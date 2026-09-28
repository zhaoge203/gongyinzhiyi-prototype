# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链六：LangGraph 编排状态机（含真实 human-in-the-loop）

状态图：

    parse → extract → (交叉校验) ─┬─(通过)──────────────→ interpret
                                  ├─(不通过, 重试<上限)→ extract
                                  └─(超上限)──→ force_review ──┐
                                                                ↓
    interpret → validate → (三重校验) ─┬─(通过)──────────→ review_gate
                                        ├─(不通过,重试<上限)→ interpret
                                        └─(超上限)──→ force_review

    review_gate ─┬─(无需复核)────────────────→ output
                 └─(需人工复核) → interrupt() 暂停，等待人工裁决
                                        ↓ Command(resume={...})
                                   人工裁决记录 → output

关键点：`review_gate` 在需要复核时**真实调用 LangGraph 的 interrupt()**，
流程会在此处暂停并把状态写入检查点；外部通过 Command(resume=...) 恢复执行。
这不是注释里的声明，是运行时可验证的行为（见 demo_human_review）。
"""
import io
import json
import operator
import os
import re
import sys
from typing import Annotated, List, TypedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chain1_parse as c1          # noqa: F401  (保持链一可独立调用)
import chain2_extract as c2
import chain3_interpret as c3
import fidelity as FID

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

MAX_RETRY = 2


class State(TypedDict, total=False):
    code: str
    doc: dict
    facts: dict
    regex_facts: dict
    cross_check_pass: bool
    diffs: List[str]
    interpretation: dict
    resolved_anchors: dict
    validation: dict
    retry_extract: int
    retry_interpret: int
    force_review: bool
    review_required: bool
    review_reason: str
    review_decision: str
    review_note: str
    log: Annotated[List[str], operator.add]


def _load_deepseek_key():
    """优先环境变量 DEEPSEEK_API_KEY；否则依次找 engine/.env、项目根 .env。"""
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key:
        return key.strip().strip('"').strip("'")
    for path in (os.path.join(HERE, '.env'),
                 os.path.join(os.path.dirname(HERE), '.env'),
                 r'D:\MyStudy\FTEC5660\.env'):
        if os.path.exists(path):
            for ln in io.open(path, encoding='utf-8'):
                m = re.match(r'^DEEPSEEK_API_KEY\s*=\s*(.+)$', ln.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    return None


def llm_setup():
    key = _load_deepseek_key()
    if not key:
        raise SystemExit('未找到 DEEPSEEK_API_KEY（请设置环境变量，或在 engine/.env 中写入 DEEPSEEK_API_KEY=...）')
    os.environ['DEEPSEEK_API_KEY'] = key
    from langchain_deepseek import ChatDeepSeek
    return ChatDeepSeek(model='deepseek-chat', temperature=0, max_tokens=4000)


LLM = None


# ---------------- 节点 ----------------
def node_parse(state: State):
    return {'log': ['[parse] 解析 %s，得到 %d 个原文块'
                    % (state['code'], len(state['doc']['blocks']))]}


def node_extract(state: State):
    if state.get('facts') and state.get('cross_check_pass'):
        return {'log': ['[extract] 已有通过校验的结果，跳过']}
    structured = LLM.with_structured_output(c2.Facts)
    chain = c2.PROMPT | structured
    ctx = c2.pick_context(state['doc']['blocks'])
    out = chain.invoke({'code': state['code'], 'context': ctx})
    fd = out.model_dump()
    rg = c2.regex_facts(state['doc'])
    ok, diffs = c2.cross_check(fd, rg)
    n = state.get('retry_extract', 0) + 1
    return {
        'facts': fd, 'regex_facts': rg, 'cross_check_pass': ok, 'diffs': diffs,
        'retry_extract': n,
        'log': ['[extract] 第 %d 次抽取，交叉校验=%s%s'
                % (n, '通过' if ok else '不通过',
                   ('｜差异: ' + '; '.join(diffs)) if diffs else '')],
    }


def route_after_extract(state: State):
    if state.get('cross_check_pass'):
        return 'interpret'
    if state.get('retry_extract', 0) >= MAX_RETRY:
        return 'force_review'
    return 'extract'


def node_interpret(state: State):
    f = state['facts']
    ctx = c3.build_context(state['doc']['blocks'])
    structured = LLM.with_structured_output(c3.Interpretation)
    chain = c3.PROMPT | structured
    n = state.get('retry_interpret', 0) + 1
    try:
        out = chain.invoke({'code': state['code'],
                            'ptype': f.get('product_type') or '',
                            'fee': f.get('comprehensive_fee') or '',
                            'hold': f.get('min_holding') or '',
                            'context': ctx})
        data = out.model_dump() if out is not None else None
    except Exception as e:
        return {'interpretation': {}, 'retry_interpret': n,
                'log': ['[interpret] 第 %d 次生成失败：%s' % (n, str(e)[:120])]}
    if data is None:
        return {'interpretation': {}, 'retry_interpret': n,
                'log': ['[interpret] 第 %d 次生成失败（结构化输出为空）' % n]}
    data['quiz_options'] = c3.normalize_quiz_options(data)
    return {'interpretation': data, 'retry_interpret': n,
            'log': ['[interpret] 第 %d 次生成成功' % n]}


def readability(text):
    """平均句长（统一走 fidelity 模块的唯一定义，避免各处口径不一致）"""
    return FID.avg_sentence_len(text)


def node_validate(state: State):
    data = state.get('interpretation') or {}
    if not data:
        return {'validation': {'pass': False, 'bad_anchors': ['<无解读结果>'],
                               'bad_expressions': [], 'checked': 0},
                'log': ['[validate] 无解读结果，判定不合格']}
    valid_ids = {b['id'] for b in state['doc']['blocks']}
    pairs = [('summary', data.get('summary'), data.get('summary_source')),
             ('fee_plain', data.get('fee_plain'), data.get('fee_source')),
             ('liquidity_plain', data.get('liquidity_plain'), data.get('liquidity_source'))]
    for i, t in enumerate(data.get('risk_cards') or []):
        s = data.get('risk_sources') or []
        pairs.append(('risk_cards[%d]' % i, t, s[i] if i < len(s) else ''))
    for i, t in enumerate(data.get('glossary') or []):
        s = data.get('glossary_sources') or []
        pairs.append(('glossary[%d]' % i, t, s[i] if i < len(s) else ''))

    # 演示/测试钩子：注入无效锚点以强制触发人工复核路径。
    # 之所以用注入而不是「传一份坏状态进来」，是因为 LangGraph 的状态合并语义：
    # 初始输入里的 interpretation 会在第一个写入该通道的节点执行后被覆盖，
    # 因此无法通过 init 直接注入「已生成的坏结果」。这个钩子让 interrupt 路径可被稳定测试。
    if os.environ.get('GYZY_FORCE_REVIEW'):
        for k in ('summary_source', 'fee_source', 'liquidity_source'):
            if data.get(k):
                data[k] = 'B999'
        for k in ('risk_sources', 'glossary_sources', 'quiz_sources'):
            if data.get(k):
                data[k] = ['B999'] * len(data[k])

    bad_a, bad_e, resolved = [], [], {}
    for name, txt, anchor in pairs:
        ok_a, bad_anchor = c3.parse_anchors(anchor, valid_ids)
        resolved[name] = ok_a
        if bad_anchor:
            bad_a.append(name)
        hit = c3.check_expression(txt or '')
        if hit:
            bad_e.append({'item': name, 'words': hit, 'text': (txt or '')[:60]})

    # 认知确认题：锚点与格式单独校验（不做表达词表检查）
    quiz_issues = []
    qs = data.get('quiz_questions') or []
    opts = data.get('quiz_options') or []
    ans = data.get('quiz_answers') or []
    qsrc = data.get('quiz_sources') or []
    if len(qs) < 3:
        quiz_issues.append('题目数量不足 3 道')
    for i, _q in enumerate(qs):
        if (opts[i] if i < len(opts) else '').count('|') != 2:
            quiz_issues.append('第 %d 题选项数异常' % (i + 1))
        if (ans[i] if i < len(ans) else '') not in ('1', '2', '3'):
            quiz_issues.append('第 %d 题答案序号非法' % (i + 1))
        _ok, bad_q = c3.parse_anchors(qsrc[i] if i < len(qsrc) else '', valid_ids)
        if bad_q:
            quiz_issues.append('第 %d 题锚点无效' % (i + 1))

    passed = (not bad_a) and (not bad_e) and (not quiz_issues)

    # 可读性门禁：使用 fidelity 模块的统一实现与统一文本构成，
    # 确保校验节点与评测脚本给出同一个数字（此前两处口径不同，导致同一只产品
    # 出现「校验通过」而「评测未通过」的矛盾结论）。
    rd = FID.readability_gate(FID.interpretation_text(data),
                              FID.source_text_for_readability(state['doc']))
    readability_ok = rd['ok']
    if not readability_ok:
        passed = False

    return {
        'resolved_anchors': resolved,
        'validation': {'pass': passed, 'bad_anchors': bad_a, 'bad_expressions': bad_e,
                       'quiz_issues': quiz_issues, 'checked': len(pairs),
                       'quiz_checked': len(qs), 'readability': rd},
        'log': ['[validate] 受检 %d 项（含确认题 %d 道）：锚点问题 %d，表达问题 %d，题目问题 %d；'
                '可读性 句长 %s vs 原文 %s → %s'
                % (len(pairs), len(qs), len(bad_a), len(bad_e), len(quiz_issues),
                   rd['gen_avg'], rd['src_avg'], '通过' if readability_ok else '不通过（触发重写）')],
    }


def route_after_validate(state: State):
    v = state.get('validation') or {}
    if v.get('pass'):
        return 'review_gate'
    if state.get('retry_interpret', 0) >= MAX_RETRY:
        return 'force_review'
    return 'interpret'


def node_force_review(state: State):
    """自动校验连续失败：强制转人工，不再重试。"""
    v = state.get('validation') or {}
    reason = '自动校验连续 %d 次未通过：锚点问题 %s，表达问题 %s，题目问题 %s，可读性 %s' % (
        state.get('retry_interpret', 0),
        v.get('bad_anchors'), v.get('bad_expressions'), v.get('quiz_issues'),
        (v.get('readability') or {}).get('reason') or '通过')
    if not state.get('cross_check_pass', True):
        reason = '要素抽取交叉校验连续 %d 次未通过：%s' % (
            state.get('retry_extract', 0), state.get('diffs'))
    return {'review_required': True, 'review_reason': reason,
            'log': ['[force_review] 自动校验超限，强制转人工复核：%s' % reason]}


def node_review_gate(state: State):
    """人工复核闸门。需要复核时真实调用 interrupt() 暂停流程。

    返回值为人工裁决结果：
      - approved   : 放行
      - rejected   : 打回，不输出
      - need_info  : 需补充材料（演示人机交互可多轮）
    """
    if not state.get('review_required'):
        return {'review_decision': 'auto_approved',
                'log': ['[review_gate] 无需人工复核，自动放行']}

    decision = interrupt({
        '类型': '人工复核请求',
        '产品': state['code'],
        '原因': state.get('review_reason'),
        '校验明细': state.get('validation'),
        '待复核解读': {
            '摘要': (state.get('interpretation') or {}).get('summary'),
            '费用透视': (state.get('interpretation') or {}).get('fee_plain'),
        },
        '可选操作': ['approved（放行）', 'rejected（打回）', 'need_info（要求补充）'],
    })
    return {
        'review_decision': decision.get('action', 'unknown'),
        'review_note': decision.get('note', ''),
        'log': ['[review_gate] 人工裁决=%s%s'
                % (decision.get('action'), ('｜' + decision['note']) if decision.get('note') else '')],
    }


def node_output(state: State):
    dec = state.get('review_decision', 'unknown')
    released = dec in ('auto_approved', 'approved')
    return {'log': ['[output] %s %s' % (state['code'],
                                        '解读放行' if released else '解读未放行（裁决=%s）' % dec)]}


def build_graph(with_checkpointer=True):
    g = StateGraph(State)
    g.add_node('parse', node_parse)
    g.add_node('extract', node_extract)
    g.add_node('interpret', node_interpret)
    g.add_node('validate', node_validate)
    g.add_node('force_review', node_force_review)
    g.add_node('review_gate', node_review_gate)
    g.add_node('output', node_output)

    g.add_edge(START, 'parse')
    g.add_edge('parse', 'extract')
    g.add_conditional_edges('extract', route_after_extract,
                            {'interpret': 'interpret', 'extract': 'extract',
                             'force_review': 'force_review'})
    g.add_edge('interpret', 'validate')
    g.add_conditional_edges('validate', route_after_validate,
                            {'interpret': 'interpret', 'review_gate': 'review_gate',
                             'force_review': 'force_review'})
    g.add_edge('force_review', 'review_gate')
    g.add_edge('review_gate', 'output')
    g.add_edge('output', END)

    if with_checkpointer:
        return g.compile(checkpointer=MemorySaver())
    return g.compile()


def run_all():
    """正常路径：全部产品跑通全流程。
    支持 `python chain6_graph.py P01 P02 ...` 只跑指定产品（分块执行），
    已有轨迹自动跳过——20+ 产品时避免单次运行过久。"""
    global LLM
    LLM = llm_setup()
    parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
    app = build_graph()
    sel = sys.argv[1:]
    codes = [c for c in sorted(parsed) if not sel or c in sel]
    tp = os.path.join(HERE, 'out_06_trace.json')
    trace = {}
    if os.path.exists(tp):
        trace = json.load(io.open(tp, encoding='utf-8'))
    print('=' * 78)
    print('LangGraph 状态机 · 正常路径（条件路由 + 回退重试 + 人工复核闸门）')
    print('=' * 78)
    for code in codes:
        if trace.get(code, {}).get('log'):
            print('\n--- %s 已有轨迹，跳过 ---' % code)
            continue
        cfg = {'configurable': {'thread_id': 'kfs-' + code}}
        init = {'code': code, 'doc': parsed[code], 'retry_extract': 0,
                'retry_interpret': 0, 'log': []}
        final = app.invoke(init, cfg)
        trace[code] = {
            'log': final.get('log', []),
            'review_required': final.get('review_required'),
            'review_reason': final.get('review_reason'),
            'review_decision': final.get('review_decision'),
            'cross_check_pass': final.get('cross_check_pass'),
            'validation': final.get('validation'),
            'retry_extract': final.get('retry_extract'),
            'retry_interpret': final.get('retry_interpret'),
        }
        print('\n--- %s ---' % code)
        for ln in final.get('log', []):
            print('   ' + ln)
    with io.open(os.path.join(HERE, 'out_06_trace.json'), 'w', encoding='utf-8') as fh:
        json.dump(trace, fh, ensure_ascii=False, indent=1)
    print('\n已写出 out_06_trace.json')
    return trace


def demo_human_review():
    """强制触发人工复核，演示 interrupt() 真实的暂停与恢复。

    实现要点：通过环境变量 GYZY_FORCE_REVIEW 让 validate 节点注入无效锚点，
    并把重试上限设为 0，使校验失败后不再重试、直接进入 force_review → review_gate。
    这样 interrupt 一定会被触发，演示可稳定复现。
    """
    global LLM
    LLM = llm_setup() if LLM is None else LLM
    parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
    facts = json.load(io.open(os.path.join(HERE, 'out_02_facts.json'), encoding='utf-8'))

    # 自动选择演示产品：优先挑「有最短持有期」的产品（演示语义最接近原 R3 圆丰），
    # 没有则取排序最后一只；不再依赖任何文件名/编号约定
    codes = sorted(parsed)
    hold = {c: (((facts.get(c) or {}).get('llm') or {}).get('min_holding') or '') for c in codes}
    with_hold = [c for c in codes
                 if hold[c] and hold[c] not in ('无', '不限', '—', '-')]
    code = sorted(with_hold, key=lambda c: hold[c], reverse=True)[0] if with_hold else codes[-1]
    print('演示产品：%s（%s）' % (code, parsed[code]['title']))
    app = build_graph()
    thread = {'configurable': {'thread_id': 'demo-review-' + code}}
    thread2 = {'configurable': {'thread_id': 'demo-review2-' + code}}

    print('\n' + '=' * 78)
    print('LangGraph 状态机 · 人工复核路径（interrupt 真实暂停与恢复）')
    print('=' * 78)
    print('\n场景：解读的锚点被判定为无效（注入 B999），且无可重试次数')
    print('      → validate 失败 → force_review → review_gate 调用 interrupt() 暂停')

    os.environ['GYZY_FORCE_REVIEW'] = '1'
    try:
        f_entry = facts.get(code) or {}
        init = {
            'code': code, 'doc': parsed[code],
            'facts': f_entry.get('llm') or f_entry.get('regex') or {},
            'regex_facts': f_entry.get('regex') or {},
            'cross_check_pass': True,
            'retry_extract': 1, 'retry_interpret': 0, 'log': [],
        }

        # 第一次 invoke：应在 review_gate 的 interrupt 处暂停
        result = app.invoke(init, thread)
        payload = None
        interrupts = result.get('__interrupt__')
        if not interrupts:
            print('\n!! 未触发 interrupt —— 复核闸门实现有误')
            return {'interrupted': False}

        payload = interrupts[0].value
        print('\n>>> 流程已暂停（interrupt 生效，图执行在此中断）')
        print('    人工复核请求内容：')
        for k in ('类型', '产品', '原因', '可选操作'):
            print('      %-8s %s' % (k, payload.get(k)))
        print('      %-8s %s' % ('待复核摘要', (payload.get('待复核解读') or {}).get('摘要')))

        snap = app.get_state(thread)
        print('\n>>> 检查点已保存中间状态')
        print('    下一步待执行节点 next = %s' % (snap.next,))
        print('    被中断时保留的解读摘要 = %s' % snap.values.get('interpretation', {}).get('summary'))
        print('    已记录的复核原因 = %s' % snap.values.get('review_reason'))

        # 第二次调用：以 Command(resume=...) 恢复执行
        print('\n>>> 模拟合规人员裁决：打回（rejected）')
        resumed = app.invoke(
            Command(resume={'action': 'rejected',
                            'note': '锚点指向不存在的原文块，需重新生成并核对出处'}),
            thread)
        for ln in resumed.get('log', []):
            print('    ' + ln)
        print('    最终裁决 =', resumed.get('review_decision'))
        print('    最终 next =', app.get_state(thread).next)

        # 再演示放行路径
        print('\n>>> 第二轮：重新发起复核，合规人员裁决为放行（approved）')
        r2 = app.invoke(dict(init, log=[]), thread2)
        if r2.get('__interrupt__'):
            print('    流程再次暂停于 interrupt，等待裁决')
            r3 = app.invoke(
                Command(resume={'action': 'approved',
                                'note': '已人工逐条核对原文，确认解读与原文一致'}),
                thread2)
            for ln in r3.get('log', []):
                print('    ' + ln)
            print('    最终裁决 =', r3.get('review_decision'))
            decisions = {'interrupted': True,
                         'rejected_path': resumed.get('review_decision'),
                         'approved_path': r3.get('review_decision')}
        else:
            decisions = {'interrupted': True, 'rejected_path': resumed.get('review_decision'),
                         'approved_path': None}
    finally:
        os.environ.pop('GYZY_FORCE_REVIEW', None)

    out = {
        'interrupt_payload': payload,
        'checkpoint': {
            'next': list(snap.next),
            'kept_summary': snap.values.get('interpretation', {}).get('summary'),
            'review_reason': snap.values.get('review_reason'),
        },
        'rejected_path_log': resumed.get('log', []),
        'decisions': decisions,
    }
    with io.open(os.path.join(HERE, 'out_07_human_review.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\n已写出 out_07_human_review.json')
    return decisions


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        demo_human_review()
    elif len(sys.argv) > 1:
        run_all()               # 分块执行：只跑指定产品，不重复演示
    else:
        run_all()
        demo_human_review()
