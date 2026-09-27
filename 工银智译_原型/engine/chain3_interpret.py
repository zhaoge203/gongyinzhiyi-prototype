# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链三：分层解读生成（五级成果 + 逐句溯源）
链四：同类产品对照解读

生成侧硬约束：
  1) 每个结论必须携带 source_block 锚点（原文块 ID），无锚点即视为无效输出；
  2) 只允许在原文信息范围内改写表达，不得新增事实、不得改变数值；
  3) 输出经「表达适当性」过滤：拦截绝对化 / 承诺性 / 诱导性表述。
"""
import io
import json
import os
import re
from typing import Any, List

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

HERE = os.path.dirname(os.path.abspath(__file__))

# 表达适当性禁用词（合规红线）
FORBIDDEN = ['稳健', '安全', '保本', '保证收益', '推荐购买', '稳赚', '必赚',
             '无风险', '零风险', '放心买', '强烈建议', '一定', '肯定能']
# 否定前缀：出现「不保本」「无风险提示」这类否定式时不应判为违规
NEG_PREFIX = ['不', '非', '无', '没', '未', '别', '勿', '禁', '免']
# 「一定」是多义词：作副词表示确定性时违规（「一定会亏」），
# 作形容词表示「某个不确定的」时完全正常（「持有满一定时间」）。
# 只有后面紧跟这些词时，「一定」才构成绝对化表述。
CERTAIN_SUFFIX = ['会', '能', '要', '将', '是', '可以', '赚', '亏', '涨', '跌', '保']


class Interpretation(BaseModel):
    """扁平化 schema：嵌套模型会显著降低结构化输出的成功率，
    这里改为「文本 + 锚点」成对平铺，兼顾稳定性与可校验性。"""
    summary: str = Field(description="一句话摘要：不超过 60 字，说明产品本质、主要风险、最坏情形")
    summary_source: str = Field(description="支撑摘要的原文块 ID，形如 B076")
    risk_cards: List[str] = Field(description="风险清单卡片文本，3-5 条，重要风险在前，每条一句话")
    risk_sources: List[str] = Field(description="与 risk_cards 一一对应的原文块 ID 列表")
    fee_plain: str = Field(description="费用透视：把分散的费率合并讲清「我实际付出多少钱」")
    fee_source: str = Field(description="支撑费用透视的原文块 ID")
    liquidity_plain: str = Field(description="流动性说明：这笔钱多久不能动、什么情况下取不出来")
    liquidity_source: str = Field(description="支撑流动性说明的原文块 ID")
    glossary: List[str] = Field(description="术语词典，2-4 条，格式为「术语：解释」")
    glossary_sources: List[str] = Field(description="与 glossary 一一对应的原文块 ID 列表")
    # ---- 认知确认题：把「机构已告知」推进到「投资者已理解」 ----
    quiz_questions: List[str] = Field(
        description="认知确认题题干，3 道，必须针对本产品的关键风险点，"
                    "且答案必须能从原文直接判定，不得含糊")
    quiz_options: List[Any] = Field(
        description="与 quiz_questions 一一对应的选项，每题 3 个选项，"
                    "在同一个字符串内用「|」分隔，例如「会|不会|不确定」。")
    quiz_answers: List[str] = Field(
        description="与 quiz_questions 一一对应的正确答案选项序号，用 1/2/3 表示")
    quiz_sources: List[str] = Field(
        description="与 quiz_questions 一一对应的原文块 ID 列表，标注正确答案的原文依据")


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是银行财富管理条线的风险解读专员。任务：把「基金产品资料概要」的专业表述，"
     "改写成普通投资者一眼能懂的说明。\n\n"
     "必须遵守：\n"
     "1) 只做表达层面的改写，不得新增原文没有的事实，不得改变任何数值；\n"
     "2) 每个结论都必须给出 source_block 锚点（形如 B076），指向支撑它的原文块；"
     "若某个结论在给定原文中找不到支撑，就不要写；\n"
     "3) 严禁出现「稳健」「安全」「保本」「保证收益」「推荐」「一定」等评价性或承诺性词汇；\n"
     "4) 不做投资建议，不做产品之间的优劣评价，只陈述事实与后果；\n"
     "5) 面向普通投资者，用「您的钱」「取不出来」这类直白表达，避免术语堆砌；\n"
     "6) 每条解读必须拆成短句：单句不超过 35 字，用句号断开；"
     "宁可多写几句，也不要把多个信息塞进一个长句。\n"
     "7) 若必须使用专业术语，第一次出现时用一句话解释它。\n"
     "8) 认知确认题必须能检验投资者是否真的读懂了本产品的关键风险，"
     "答案必须能从原文直接判定；错误选项要看起来合理，但不能靠文字游戏误导。"),
    ("human",
     "产品代码：{code}\n基金类型：{ptype}\n运作综合费率（年化）：{fee}\n最短持有期：{hold}\n\n"
     "以下是原文块（格式为 [块ID] 原文内容）：\n\n{context}"),
])

KEY_HINT = ['费率', '费用', '管理费', '托管费', '销售服务费', '赎回', '申购', '持有期',
            '风险', '基准', '投资范围', '运作方式', '开放频率', '基金类型', '侧袋',
            '期货', '港股通', '存托凭证', '资产支持证券', '杠杆', '清算', '终止', '不提供任何保证']


def build_context(blocks, limit=9000):
    picked, seen = [], set()
    for i, b in enumerate(blocks):
        t = b['text']
        if len(t) < 2 or t in seen:
            continue
        if not (any(k in t for k in KEY_HINT) or b['section'] in (
                '投资本基金涉及的费用', '风险揭示与重要提示')):
            continue
        seen.add(t)
        lbl = '%s|第%d页' % (b['id'], b['page'])
        if i + 1 < len(blocks):
            nxt = blocks[i + 1]['text'].strip()
            if re.fullmatch(r'[\d,\.]+%?|[\d,]+\.\d{2}\s*元', nxt) and len(nxt) <= 20:
                picked.append('[%s] %s → %s' % (lbl, t, nxt))
                seen.add(nxt)
                continue
        picked.append('[%s] %s' % (lbl, t))
    return '\n'.join(picked)[:limit]


def check_expression(text):
    """表达适当性检查：返回真正违规的词。

    两处必须处理的语境问题，都是实战中真实踩到的：
      1) 否定语境：「本基金不保本」是合规的必要提示，
         若把它判为违规词，就会把正确的风险提示拦下来。
      2) 多义词：「一定」在「持有满一定时间」中是「某个不确定的」，
         与绝对化表述无关；只有「一定会/一定能/一定要」这类才是违规。
    """
    hits = []
    for w in FORBIDDEN:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            start = i + 1
            prefix = text[max(0, i - 2):i]
            if any(p in prefix for p in NEG_PREFIX):
                continue
            if w == '一定':
                nxt = text[i + len(w):i + len(w) + 2]
                if not any(nxt.startswith(s) for s in CERTAIN_SUFFIX):
                    continue          # 形容词用法，非绝对化表述
            hits.append(w)
    return sorted(set(hits))


def parse_anchors(raw, valid_ids):
    """锚点解析：模型可能返回单个块 ID，也可能返回逗号、顿号、竖线或换行分隔的多个块 ID。
    逐个核验是否真实存在于原文；返回 (合法锚点列表, 非法锚点列表)。
    注意：把这种「未归一化的多锚点」判为无效，会把正确输出误拦 —— 实战中踩过两次
    （先是逗号分隔，后是竖线分隔）。因此分隔符集合必须放宽。"""
    if not raw:
        return [], ['<空>']
    parts = [p.strip() for p in re.split(r'[,，、;；\s\|/]+', str(raw)) if p.strip()]
    parts = [p for p in parts if p not in ('|', '-')]
    ok = [p for p in parts if p in valid_ids]
    bad = [p for p in parts if p not in valid_ids]
    if not parts:
        return [], ['<空>']
    return ok, bad


def normalize_quiz_options(data):
    """选项字段归一化：模型可能返回 list，也可能返回 JSON 数组字符串（实测高频），
    还可能把选项直接拼成一个用「|」分隔的字符串。统一归一为 list[str]，
    每个元素形如「A|B|C」。这一步是纯格式修复，不改变任何文案内容。

    注意这里在 Pydantic 校验之前做了「预归一化」：由于模型倾向把 list 再编码成
    JSON 字符串，若让它直接进 schema 会触发校验失败并浪费一次重试。
    因此在调用链里先取值、归一、再放回 dict，避免无谓的重试开销。"""
    opts = data.get('quiz_options')
    if isinstance(opts, list):
        return [str(o) for o in opts]
    if isinstance(opts, str):
        s = opts.strip()
        if s.startswith('['):
            try:
                import json as _json
                v = _json.loads(s)
                if isinstance(v, list):
                    return [str(x) for x in v]
                return [str(v)]
            except Exception:
                pass
        return [s]
    return []


def main():
    key = None
    for ln in io.open(r'D:\MyStudy\FTEC5660\.env', encoding='utf-8'):
        m = re.match(r'^DEEPSEEK_API_KEY\s*=\s*(.+)$', ln.strip())
        if m:
            key = m.group(1).strip().strip('"').strip("'")
    os.environ['DEEPSEEK_API_KEY'] = key

    parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
    facts = json.load(io.open(os.path.join(HERE, 'out_02_facts.json'), encoding='utf-8'))

    llm = ChatDeepSeek(model='deepseek-chat', temperature=0, max_tokens=4000)
    structured = llm.with_structured_output(Interpretation)
    chain = PROMPT | structured

    # 回退重写链：结构化输出失败时，把失败原因回灌给模型重试
    REPAIR = ChatPromptTemplate.from_messages([
        ("system", "上一次的输出未通过结构化解析或未满足约束。请严格按字段说明重新输出，"
                   "确保每个文本字段都有对应的 source 字段，且 source 必须是输入中出现过的块 ID。"),
        ("human", "失败原因：{reason}\n\n原文块：\n\n{context}"),
    ])
    repair_chain = REPAIR | structured

    results = {}
    for code in sorted(parsed):
        doc = parsed[code]
        f = facts[code]['llm']
        valid_ids = {b['id'] for b in doc['blocks']}
        ctx = build_context(doc['blocks'])
        print('--- %s 生成中（%d 字上下文）---' % (code, len(ctx)))

        payload = {'code': code, 'ptype': f.get('product_type') or '',
                   'fee': f.get('comprehensive_fee') or '',
                   'hold': f.get('min_holding') or '', 'context': ctx}

        # 长句机械拆分为可读句子（确定性后处理，不改变语义与数值）。
        # 仅做断句，不增删任何一个字 —— 这是「不改变信息」红线的安全操作。
        def shorten(t):
            if not t:
                return t
            # 在分号/逗号后的连接词处断句，但不动数字内部的符号
            t = re.sub(r'；(?=[^0-9])', '。', t)
            t = re.sub(r'，(而且|并且|同时|另外|此外|但是|不过|因此|所以)', r'。\1', t)
            # 把过长的顿号枚举拆成短句
            parts, out = re.split(r'(?<=[。！？])', t), []
            for seg in parts:
                while len(seg) > 45:
                    cut = -1
                    for m in re.finditer(r'[，、]', seg):
                        if m.start() <= 42:
                            cut = m.start()
                    if cut <= 0:
                        break
                    out.append(seg[:cut + 1])
                    seg = seg[cut + 1:]
                out.append(seg)
            return ''.join(out)

        data, attempts, last_err = None, 0, ''
        while attempts < 3 and data is None:
            attempts += 1
            try:
                if attempts == 1:
                    interp = chain.invoke(payload)
                else:
                    interp = repair_chain.invoke({'reason': last_err, 'context': ctx})
                if interp is None:
                    last_err = '模型返回了空的结构化结果（schema 未被满足）'
                    print('   第 %d 次尝试：空结果，触发回退重写' % attempts)
                    continue
                data = interp.model_dump()
            except Exception as e:
                last_err = str(e)[:200]
                print('   第 %d 次尝试异常：%s' % (attempts, last_err))
        if data is None:
            results[code] = {'error': last_err, 'attempts': attempts}
            continue

        # 应用长句拆分后处理（只断句，不改字）
        for k in ('summary', 'fee_plain', 'liquidity_plain'):
            data[k] = shorten(data.get(k))
        data['risk_cards'] = [shorten(x) for x in (data.get('risk_cards') or [])]

        # 校验：锚点有效性 + 表达适当性
        issues = []
        pairs = [('summary', data.get('summary'), data.get('summary_source')),
                 ('fee_plain', data.get('fee_plain'), data.get('fee_source')),
                 ('liquidity_plain', data.get('liquidity_plain'), data.get('liquidity_source'))]
        for i, t in enumerate(data.get('risk_cards') or []):
            srcs = data.get('risk_sources') or []
            pairs.append(('risk_cards[%d]' % i, t, srcs[i] if i < len(srcs) else ''))
        for i, t in enumerate(data.get('glossary') or []):
            srcs = data.get('glossary_sources') or []
            pairs.append(('glossary[%d]' % i, t, srcs[i] if i < len(srcs) else ''))

        # 认知确认题的锚点与格式校验
        quiz_issues = []
        data['quiz_options'] = normalize_quiz_options(data)
        qs = data.get('quiz_questions') or []
        opts = data.get('quiz_options') or []
        ans = data.get('quiz_answers') or []
        qsrc = data.get('quiz_sources') or []
        if len(qs) < 3:
            quiz_issues.append('题目数量不足 3 道（%d）' % len(qs))
        for i, q in enumerate(qs):
            opt = (opts[i] if i < len(opts) else '')
            if opt.count('|') != 2:
                quiz_issues.append('第 %d 题选项不是 3 个：%s' % (i + 1, opt[:60]))
            a = (ans[i] if i < len(ans) else '')
            if a not in ('1', '2', '3'):
                quiz_issues.append('第 %d 题答案序号非法：%s' % (i + 1, a))
            # 题干的锚点有效性单独校验，但不进入「表达适当性」词表检查：
            # 确认题必然要问「是否保证收益」「是否安全」，用禁用词表去拦会把正确题目误判违规
            # （实测中确实发生了两次）。表达合规只审查解读正文，不审查考题。
            ok_q, bad_q = parse_anchors(qsrc[i] if i < len(qsrc) else '', valid_ids)
            if bad_q:
                quiz_issues.append('第 %d 题锚点无效：%s' % (i + 1, bad_q))

        bad_anchor, bad_expr, resolved = [], [], {}
        for name, txt, anchor in pairs:
            ok_a, bad_a = parse_anchors(anchor, valid_ids)
            resolved[name] = ok_a
            if bad_a:
                bad_anchor.append('%s→%s' % (name, bad_a))
            hit = check_expression(txt or '')
            if hit:
                bad_expr.append('%s%s' % (name, hit))

        results[code] = {
            'interpretation': data,
            'attempts': attempts,
            'resolved_anchors': resolved,
            'anchor_check_pass': not bad_anchor,
            'expression_check_pass': not bad_expr,
            'quiz_format_pass': not quiz_issues,
            'quiz_issues': quiz_issues,
            'bad_anchors': bad_anchor,
            'bad_expressions': bad_expr,
            'checked_items': len(pairs),
        }
        print('   摘要：%s' % data.get('summary'))
        print('   风险卡 %d 张 | 术语 %d 条 | 确认题 %d 道 | 尝试 %d 次 | 受检 %d 项'
              % (len(data.get('risk_cards') or []), len(data.get('glossary') or []),
                 len(qs), attempts, len(pairs)))
        print('   锚点=%s | 表达=%s | 确认题格式=%s'
              % ('通过' if not bad_anchor else '不通过 ' + str(bad_anchor),
                 '通过' if not bad_expr else '不通过 ' + str(bad_expr),
                 '通过' if not quiz_issues else '不通过 ' + str(quiz_issues)))

    with io.open(os.path.join(HERE, 'out_03_interpretation.json'), 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print('\n已写出 out_03_interpretation.json')


if __name__ == '__main__':
    main()
