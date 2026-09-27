# -*- coding: utf-8 -*-
"""从 example 的四份真实产品资料概要中抽取关键要素，生成可用于策划案的对照表。
只做客观抽取与核对，不做任何推测性补全；抽取不到的字段标注「文件未单独列示」。
"""
import io, os, re, glob, sys
sys.path.insert(0, r'D:\MyStudy\.pdftools')
import pypdf

SRC = r'D:\MyStudy\工行杯\example'
OUT = r'D:\MyStudy\工银智译_生成源文件\extract_result.txt'

# 顺序：R1 货币 -> R2 纯债 -> R3 三年持有期混合 -> R4 股票
FILES = sorted(glob.glob(os.path.join(SRC, '*.pdf')))
buf = io.StringIO()


def w(s=''):
    buf.write(str(s) + '\n')


def norm(t):
    """去掉页眉页脚与多余空白，便于正则匹配"""
    t = t.replace('\u3000', ' ')
    lines = []
    for ln in t.split('\n'):
        s = ln.strip()
        if not s:
            continue
        if re.match(r'^第\s*\d+\s*页\s*共\s*\d+\s*页$', s):
            continue
        if '基金产品资料概要更新' in s:
            continue
        lines.append(s)
    return '\n'.join(lines)


def grab(text, key, span=260):
    i = text.find(key)
    if i < 0:
        return None
    return text[i + len(key):i + len(key) + span].replace('\n', ' ').strip()


STOP = ['基金托管人', '基金合同生效日', '上市交易所', '基金类型', '交易币种',
        '运作方式', '开放频率', '基金经理', '开始担任', '证券从业日期', '下属基金简称',
        '基金管理人', '基金代码', '二、', '一、', '其他']


def grabfield(text, key):
    """取 key 之后、下一个已知字段标签之前的内容"""
    v = grab(text, key, 400)
    if v is None:
        return None
    cut = len(v)
    for s in STOP:
        j = v.find(s)
        if 0 <= j < cut:
            cut = j
    v = v[:cut].strip(' |')
    return v or None


recs = []
for f in FILES:
    r = pypdf.PdfReader(f)
    raw = '\n'.join((p.extract_text() or '') for p in r.pages)
    t = norm(raw)
    name = os.path.basename(f)

    rec = {}
    m = re.search(r'^(工银瑞信[^\n]*?(?:基金|证券投资基金))\s*$', raw, re.M)
    rec['file'] = name
    rec['fullname'] = m.group(1).strip() if m else '?'

    # 基金类型 / 运作方式 / 开放频率
    for k in ['基金类型', '运作方式', '开放频率', '基金代码']:
        rec[k] = grabfield(t, k)

    # 风险收益特征
    rec['风险收益特征'] = grab(t, '风险收益特征', 230)
    # 综合费率
    m = re.search(r'基金运作综合费率（年化）\s*([\d.]+%)', t)
    rec['综合费率'] = m.group(1) if m else None
    # 管理费/托管费/销售服务费：先定位到"基金运作相关费用"段落再取，避免串到别处
    seg = t
    i = t.find('基金运作相关费用')
    if i > 0:
        seg = t[i:i + 900]
    for k in ['管理费', '托管费', '销售服务费']:
        m = re.search(re.escape(k) + r'\s*([\d.]+%)', seg)
        rec[k] = m.group(1) if m else None
    # 最短持有期
    m = re.search(r'([一二三四五六七八九十\d]+)\s*年最短持有期', t)
    rec['最短持有期'] = (m.group(1) + '年') if m else None
    m2 = re.search(r'最短持有期[限]?[，,]?\s*([^\n。]{0,40})', t)
    rec['最短持有期原句'] = m2.group(0).strip() if m2 else None
    # 是否不收取赎回费
    rec['赎回费说明'] = '不收取赎回费' if re.search(r'本基金不收取赎回费', t) else (
        '不收取申购和赎回费用' if re.search(r'本基金不收取申购费用和赎回费用', t) else None)
    # 特有风险关键词
    keys = ['侧袋机制', '港股通', '股指期货', '国债期货', '存托凭证', '资产支持证券',
            '最短持有期', '强制赎回费用', '巨额赎回', '科创板', '北交所', '杠杆']
    rec['出现的关键机制/风险'] = [k for k in keys if k in t]
    # 是否提及不保证本金
    rec['不保证本金表述'] = bool(re.search(r'投资者可能损失投资本金', t))
    recs.append(rec)

w('=' * 78)
w('四份真实产品资料概要 — 客观要素抽取（数据来源：工行杯/example 原始 PDF）')
w('=' * 78)
for rec in recs:
    w('')
    w('【%s】' % rec['file'])
    w('  基金全称：%s' % rec['fullname'])
    w('  基金类型：%s' % rec['基金类型'])
    w('  运作方式：%s' % rec['运作方式'])
    w('  开放频率：%s' % rec['开放频率'])
    w('  综合费率(年化)：%s' % rec['综合费率'])
    w('  管理费/托管费/销售服务费：%s / %s / %s' % (rec['管理费'], rec['托管费'], rec['销售服务费']))
    w('  最短持有期：%s' % rec['最短持有期'])
    w('  申赎费用说明：%s' % rec['赎回费说明'])
    w('  风险收益特征：%s' % rec['风险收益特征'])
    w('  出现的关键机制/风险：%s' % '、'.join(rec['出现的关键机制/风险']))
    w('  含"投资者可能损失投资本金"：%s' % rec['不保证本金表述'])

w('')
w('=' * 78)
w('横向对照表（拟用于策划案）')
w('=' * 78)
hdr = ['项目', 'R1 如意货币', 'R2 信用纯债A', 'R3 圆丰三年持有期混合', 'R4 创新动力股票']
rows = [
    ['基金类型'] + [r['基金类型'] for r in recs],
    ['运作方式 / 开放频率'] + ['%s / %s' % (r['运作方式'], r['开放频率']) for r in recs],
    ['运作综合费率（年化）'] + [r['综合费率'] for r in recs],
    ['管理费 / 托管费 / 销售服务费'] + ['%s / %s / %s' % (r['管理费'], r['托管费'], r['销售服务费']) for r in recs],
    ['最短持有期'] + [(r['最短持有期'] or '无') for r in recs],
    ['赎回费'] + [(r['赎回费说明'] or '见费率表') for r in recs],
    ['关键机制 / 特有风险'] + ['、'.join(r['出现的关键机制/风险']) for r in recs],
]
for h, *cells in zip(hdr, *rows):
    w(' | '.join([h] + list(cells)))

io.open(OUT, 'w', encoding='utf-8').write(buf.getvalue())
print(buf.getvalue())
