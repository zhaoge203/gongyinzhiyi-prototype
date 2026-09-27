# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链一：文档解析与语义分块
输入：官方基金产品资料概要 PDF
输出：结构化章节 + 带元数据标签的条款块 + 位置锚点（页码 / 块序号）

设计要点：锚点是后续「逐句溯源」的唯一依据，因此每个块必须携带
可回到原文的定位信息（页码 + 原文片段），不做任何改写。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\MyStudy\.pdftools')
import pypdf

PDF_DIR = r'D:\MyStudy\工行杯\example'
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# 章节标题（KFS 固定结构）
SECTION_PAT = re.compile(
    r'^\s*([一二三四五六七八九十]+)\s*[、.]\s*(产品概况|基金投资与净值表现|投资本基金涉及的费用|风险揭示与重要提示|其他资料查询方式|其他情况说明)\s*$'
)
SUB_PAT = re.compile(r'^\s*[（(]\s*([一二三四五六七八九十]+)\s*[)）]\s*(.+?)\s*$')

# 页眉页脚噪声：只过滤确认无疑的页眉页脚与空行。
# 注意：不能按「行太短」来过滤 —— KFS 的费率数值常单独成行（如「0.45%」），
# 一旦被当作噪声丢掉，后续抽取就拿不到值。这里保留所有含数字/百分号的短行。
NOISE = [
    re.compile(r'^第\s*\d+\s*页\s*共\s*\d+\s*页$'),
    re.compile(r'基金产品资料概要(更新)?$'),
    re.compile(r'^\s*$'),
]


def is_noise(line):
    if re.search(r'[\d%]', line):      # 含数字或百分号的行一律保留
        return False
    return any(p.search(line) for p in NOISE)

# 风险要素关键词 -> 风险类别（用于打标签，不改变原文）
RISK_TAGS = {
    '流动性风险': ['流动性', '赎回', '变现', '最短持有期', '侧袋', '巨额赎回', '强制赎回'],
    '市场风险': ['市场波动', '证券市场波动', '股价', '指数', '净值波动', '利率'],
    '信用风险': ['信用风险', '违约', '信用'],
    '杠杆风险': ['杠杆', '保证金', '期货', '强制平仓'],
    '汇率与跨境风险': ['汇率', '港股通', '境外', '香港'],
    '操作与合规风险': ['操作风险', '合规性风险', '管理风险'],
    '机制特有风险': ['侧袋机制', '存托凭证', '资产支持证券', '科创板', '新股', '申购'],
}

MONEY_KEYS = ['管理费', '托管费', '销售服务费', '审计费用', '信息披露费']


def tag_risk(text):
    tags = []
    for cat, kws in RISK_TAGS.items():
        if any(k in text for k in kws):
            tags.append(cat)
    return tags


def parse_pdf(path):
    reader = pypdf.PdfReader(path)
    doc = {
        'file': os.path.basename(path),
        'pages': len(reader.pages),
        'title': None,
        'blocks': [],
    }
    cur_sec = None
    cur_sub = None

    for pno, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ''
        for ln in raw.split('\n'):
            line = ln.replace('\u3000', ' ').strip()
            if is_noise(line):
                continue
            if doc['title'] is None and '基金' in line and ('概要' not in line):
                doc['title'] = line
            m = SECTION_PAT.match(line)
            if m:
                cur_sec, cur_sub = m.group(2), None
                continue
            m2 = SUB_PAT.match(line)
            if m2 and len(line) < 40:
                cur_sub = m2.group(2)
                continue
            if len(line) < 2:
                continue
            doc['blocks'].append({
                'id': 'B%03d' % (len(doc['blocks']) + 1),
                'page': pno,
                'section': cur_sec,
                'subsection': cur_sub,
                'text': line,
                'risk_tags': tag_risk(line),
            })
    return doc


def main():
    files = sorted(f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf'))
    out = {}
    for f in files:
        code = f.split('-')[0].strip()
        d = parse_pdf(os.path.join(PDF_DIR, f))
        d['code'] = code
        out[code] = d
        tagged = sum(1 for b in d['blocks'] if b['risk_tags'])
        print('%-4s %-46s 页=%-2d 块=%-4d 带风险标签=%-3d' % (
            code, d['title'] or f, d['pages'], len(d['blocks']), tagged))

    with io.open(os.path.join(OUT_DIR, 'out_01_parsed.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\n已写出 out_01_parsed.json')


if __name__ == '__main__':
    main()
