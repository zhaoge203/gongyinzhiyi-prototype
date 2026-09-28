# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链一：文档解析与语义分块
输入：官方基金产品资料概要 PDF
输出：结构化章节 + 带元数据标签的条款块 + 位置锚点（页码 / 块序号）

设计要点：锚点是后续「逐句溯源」的唯一依据，因此每个块必须携带
可回到原文的定位信息（页码 + 原文片段），不做任何改写。
"""
import hashlib
import io
import json
import os
import re
import sys

import pypdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(os.path.dirname(HERE), 'data')
if not os.path.isdir(PDF_DIR):
    PDF_DIR = r'D:\MyStudy\工行杯\example'  # 兼容旧环境
OUT_DIR = HERE

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


def _title_ok(t):
    """标题 sanity check：太长或带正文书写的标题视为抓取失败。"""
    return bool(t) and len(t) <= 30 and not re.search(r'[；;。，,、：:]', t)


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
    # 标题兜底：内容抓取不合格时用文件名做展示名（仅显示用途，不做任何解析依赖）
    if not _title_ok(doc['title']):
        doc['title'] = re.sub(r'\.pdf$', '', os.path.basename(path), flags=re.I)
        doc['title_source'] = 'filename'
    else:
        doc['title_source'] = 'content'
    return doc


def main():
    # 递归扫描 data/ 下所有子文件夹；文件名不做任何假设；
    # 按内容 MD5 去重（同一产品放了两份只解析一次）；代号按扫描顺序自动编号 P01、P02……
    out = {}
    seen = {}
    n = 0
    for dirpath, _, filenames in os.walk(PDF_DIR):
        for f in sorted(filenames):
            if not f.lower().endswith('.pdf'):
                continue
            path = os.path.join(dirpath, f)
            with open(path, 'rb') as fh:
                h = hashlib.md5(fh.read()).hexdigest()
            rel = os.path.relpath(path, PDF_DIR)
            if h in seen:
                print('跳过重复文件：%s（内容同 %s）' % (rel, seen[h]))
                continue
            n += 1
            code = 'P%02d' % n
            seen[h] = rel
            d = parse_pdf(path)
            d['code'] = code
            out[code] = d
            tagged = sum(1 for b in d['blocks'] if b['risk_tags'])
            print('%-4s %-46s 页=%-2d 块=%-4d 带风险标签=%-3d' % (
                code, d['title'] or f, d['pages'], len(d['blocks']), tagged))

    with io.open(os.path.join(OUT_DIR, 'out_01_parsed.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\n共解析 %d 份文档，已写出 out_01_parsed.json' % n)


if __name__ == '__main__':
    main()
