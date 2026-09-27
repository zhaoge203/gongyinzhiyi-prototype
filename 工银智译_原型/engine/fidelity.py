# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链五（重构）：上下文一致性保真度校验

为什么重构
----------
原实现是「解读中的百分比是否在原文任意位置出现过」，只要数值在原文任何地方出现
就给满分。实测该指标对 7 类语义错配全部漏检：把「托管费 0.2%」说成「管理费 0.2%」、
把申购费 1.5% 说成赎回费、把「60%–95%」说成「5%–95%」、把年化说成月费率……
数值全是真的，语义全错，指标全过。

新实现回答的是另一个问题：
    「这个数值，在原文里是不是挂在同一个标签下？」
即校验 (标签, 数值) 配对的**上下文一致性**，而非数值的存在性。

判定规则
--------
1. 从解读文本中抽取 (标签, 数值) 混合对，例如「管理费1.2%」→ (管理费, 1.2%)。
2. 在解读所绑定的原文锚点块中，查找该标签所在的「标签—数值窗口」
   （锚点块自身 + 其相邻块，以覆盖 PDF 表格被压平的常见情形）。
3. 该数值必须出现在同一窗口中，否则判为「跨处引用」——即数值真实但归属错误。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# 标签别名映射：把解读中的自然表达归一到原文使用的字段名
LABEL_ALIASES = {
    '管理费': ['管理费', '管理费率', '管理费年费率'],
    '托管费': ['托管费', '托管费率', '托管费年费率'],
    '销售服务费': ['销售服务费', '销售服务费率'],
    '申购费': ['申购费', '申购费率', '认购费', '认购费率', '买入费'],
    '赎回费': ['赎回费', '赎回费率', '卖出费'],
    '综合费率': ['运作综合费率', '综合费率', '基金运作综合费率'],
    '审计费': ['审计费', '审计费用'],
    '信息披露费': ['信息披露费', '信息披露费用'],
    '持有期': ['最短持有期', '最短持有期限', '持有期'],
    '投资比例': ['投资比例', '占基金资产的比例', '占基金资产净值'],
}

# 解读中的「标签 + 数值」混合模式。
# 关键约束：中间的间隔字符不得跨越句子边界（。；！？换行），
# 否则会跨界误配 —— 例如「…有3年最短持有期，运作综合费率年化1.40%」
# 曾把「持有期」与「1.40%」配成一对（实战踩过）。
LABEL_GROUP = '|'.join(
    sorted({a for al in LABEL_ALIASES.values() for a in al}, key=len, reverse=True))
PATTERN = re.compile(
    r'(?P<label>' + LABEL_GROUP + r')'
    r'(?!期间|期内|期间内)'        # 排除「持有期间」这类非标签用法
    r'[^\d%。；！？\n]{0,12}?'
    r'(?P<value>\d+(?:\.\d+)?%)'
)

# 纯数值（用于统计「未挂标签的数字」）
NUM_PAT = re.compile(r'\d+(?:\.\d+)?%')

# 标签—数值窗口的最大块数。
# 「投资本基金涉及的费用」一节含费率表，实测被压平为 38 个块，
# 因此阈值必须高于该量级，否则会退化为邻近半径窗口并造成大量误报。
MAX_WINDOW_BLOCKS = 80
FALLBACK_RADIUS = 3

# 费率类标签天然跨小节分布：KFS 里「申购费/赎回费」属「基金销售相关费用」，
# 「管理费/托管费/销售服务费」属「基金运作相关费用」，
# 二者同属「投资本基金涉及的费用」这一节。
# 因此对费率类标签，窗口放宽到「节」级；其余标签仍用「小节」级，
# 以免把「风险揭示」等大段落混进来造成误配。
SECTION_LEVEL_LABELS = {'管理费', '托管费', '销售服务费', '申购费', '赎回费',
                        '综合费率', '审计费', '信息披露费'}


def canonical(label):
    for canon, alts in LABEL_ALIASES.items():
        if label in alts:
            return canon
    return label


def extract_metrics(text):
    """抽取 (规范标签, 数值) 对。

    额外施加「邻接性」约束：标签与数值之间的间隙不得跨越句子边界，
    且间隙内的字符数受限。这是必要的，否则「…有3年最短持有期，运作综合费率年化1.40%」
    会把「持有期」与「1.40%」配成一对，产生假阳性（实测踩过）。
    把这类无法确定归属的数值交回给「未挂标签的数值」统计，而不是硬配一对。
    """
    out = []
    for m in PATTERN.finditer(text or ''):
        gap = m.group(0)[len(m.group('label')):len(m.group(0)) - len(m.group('value'))]
        out.append((canonical(m.group('label')), m.group('value'), gap))
    return out


def extract_pairs(text):
    return [(l, v) for l, v, _g in extract_metrics(text)]


def window_text(block_id, blocks_by_id, source_blocks, label=None):
    """构造「标签—数值窗口」。

    KFS 的费率表经 PDF 抽取后被压平成多行，同一张表的行可能相隔十几个块，
    固定 ±1 的邻近窗口会漏掉本该在范围内的数值（实测导致大量误报）。

    取窗策略按标签类型分两档：
      - 费率类标签：取「节」级范围（如整个「投资本基金涉及的费用」），
        因为申购赎回费与运作费用本就分处不同小节。
      - 其他标签：取「小节」级范围；若小节过长则退化为锚点附近固定半径。
    """
    if block_id not in blocks_by_id:
        return ''
    idx = blocks_by_id[block_id]
    anchor_block = source_blocks[idx]
    sec = anchor_block.get('section')
    sub = anchor_block.get('subsection')

    if label in SECTION_LEVEL_LABELS:
        scope = [i for i, b in enumerate(source_blocks) if b.get('section') == sec]
    else:
        scope = [i for i, b in enumerate(source_blocks)
                 if b.get('section') == sec and b.get('subsection') == sub]

    if scope and len(scope) <= MAX_WINDOW_BLOCKS:
        return '\n'.join(source_blocks[i]['text'] for i in scope)

    lo, hi = max(0, idx - FALLBACK_RADIUS), min(len(source_blocks) - 1, idx + FALLBACK_RADIUS)
    return '\n'.join(source_blocks[i]['text'] for i in range(lo, hi + 1))


def check_text(text, anchors, source_blocks, blocks_by_id, full_text=''):
    """校验一段解读文本。

    对每个 (标签, 数值) 对，在锚点所在小节的窗口内查找同一标签下的该数值：
      - 找到            → grounded（落地）
      - 未找到，但该数值在全文其他地方出现 → misattributed（跨处引用：数值真实但归属可疑）
      - 未找到且全文也没有            → unsupported（原文不支持）
    未挂标签的纯数值单独统计，不计入保真度分母。
    """
    ok, mis, unsupported = [], [], []
    for label, value in extract_pairs(text):
        grounded = False
        if anchors:
            for a in anchors:
                win = window_text(a, blocks_by_id, source_blocks, label)
                if label in win and value in win:
                    grounded = True
                    break
        if grounded:
            ok.append((label, value))
        elif value in full_text:
            mis.append((label, value))
        else:
            unsupported.append((label, value))
    tagged = {v for _l, v in extract_pairs(text)}
    untagged = sorted(set(NUM_PAT.findall(text or '')) - tagged)
    return ok, mis, unsupported, untagged


def build_index(parsed_doc):
    return {b['id']: i for i, b in enumerate(parsed_doc['blocks'])}


# ---------- 可读性度量：全项目唯一定义，避免各处口径不一致 ----------
READABILITY_TOL = 1.20      # 允许比原文长 20% 以内
READABILITY_MAX = 30.0      # 绝对上限（字/句）
READABILITY_SECTIONS = ('风险揭示与重要提示', '投资本基金涉及的费用')


def avg_sentence_len(text):
    sents = [s for s in re.split(r'[。；！？\n]', text or '') if s.strip()]
    if not sents:
        return 0.0
    return round(sum(len(s) for s in sents) / len(sents), 1)


def interpretation_text(data):
    """解读侧用于可读性度量的文本构成 —— 与校验节点保持一致"""
    parts = [data.get('summary', ''), data.get('fee_plain', ''),
             data.get('liquidity_plain', '')]
    parts += list(data.get('risk_cards') or [])
    return '\n'.join(p for p in parts if p)


def source_text_for_readability(parsed_doc):
    """原文侧基线：投资者真正需要阅读的两个章节（风险揭示 + 费用）"""
    return '\n'.join(b['text'] for b in parsed_doc['blocks']
                     if b.get('section') in READABILITY_SECTIONS)


def readability_gate(gen_text, src_text):
    g, s = avg_sentence_len(gen_text), avg_sentence_len(src_text)
    over_tol = g > s * READABILITY_TOL
    over_max = g > READABILITY_MAX
    return {
        'gen_avg': g, 'src_avg': s,
        'ok': (not over_tol) and (not over_max),
        'reason': '句长超出容差' if over_tol else ('句长超出绝对上限' if over_max else ''),
        'tolerance': READABILITY_TOL, 'absolute_max': READABILITY_MAX,
    }


def evaluate(interp_result, parsed_doc):
    data = interp_result.get('interpretation') or {}
    anchors_map = interp_result.get('resolved_anchors') or {}
    blocks = parsed_doc['blocks']
    idx = build_index(parsed_doc)
    full_text = '\n'.join(b['text'] for b in blocks)

    fields = [
        ('summary', data.get('summary'), anchors_map.get('summary') or []),
        ('fee_plain', data.get('fee_plain'), anchors_map.get('fee_plain') or []),
        ('liquidity_plain', data.get('liquidity_plain'), anchors_map.get('liquidity_plain') or []),
    ]
    for i, t in enumerate(data.get('risk_cards') or []):
        fields.append(('risk_cards[%d]' % i, t, anchors_map.get('risk_cards[%d]' % i) or []))
    for i, t in enumerate(data.get('glossary') or []):
        fields.append(('glossary[%d]' % i, t, anchors_map.get('glossary[%d]' % i) or []))

    total_ok, all_mis, all_unsup, all_untagged = 0, [], [], []
    detail = []
    for name, text, anchors in fields:
        ok, mis, unsup, untagged = check_text(text, anchors, blocks, idx, full_text)
        total_ok += len(ok)
        all_mis.extend({'field': name, 'label': l, 'value': v} for l, v in mis)
        all_unsup.extend({'field': name, 'label': l, 'value': v} for l, v in unsup)
        all_untagged.extend({'field': name, 'value': v} for v in untagged)
        if mis or unsup or untagged:
            detail.append({'field': name, 'misattributed': mis,
                           'unsupported': unsup, 'untagged': untagged})

    n = total_ok + len(all_mis) + len(all_unsup)
    return {
        'grounded_pairs': total_ok,
        'misattributed_pairs': all_mis,
        'unsupported_pairs': all_unsup,
        'total_labeled_pairs': n,
        'context_fidelity_pct': round(total_ok / n * 100, 1) if n else None,
        'untagged_numbers': all_untagged,
        'detail': detail,
    }
