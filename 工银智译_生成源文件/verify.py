# -*- coding: utf-8 -*-
"""校验生成的 docx：结构、编号、字数、格式"""
import io, sys, re
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

PATH = r'D:\MyStudy\工行杯\工银智译——金融产品资料概要智能解读平台策划案（包家瑞、卢欣烨）.docx'
out = io.open(r'D:\MyStudy\工银智译_生成源文件\structure.txt', 'w', encoding='utf-8')

d = Document(PATH)
body = d.element.body
paras = d.paragraphs

out.write('=== 标题结构 ===\n')
hcount = {1: 0, 2: 0, 3: 0}
for p in paras:
    st = p.style.name
    m = re.match(r'Heading (\d)', st)
    if m:
        lv = int(m.group(1))
        hcount[lv] = hcount.get(lv, 0) + 1
        out.write('%s%s\n' % ('  ' * (lv - 1), p.text))
out.write('\n标题数: %s\n' % hcount)
out.write('总段落数: %d\n' % len(paras))

out.write('\n=== 表与题注 ===\n')
caps = [p.text for p in paras if p.text.startswith('表 ')]
for c in caps:
    out.write(c + '\n')
out.write('题注数: %d  表格数: %d\n' % (len(caps), len(d.tables)))

out.write('\n=== 表格规格 ===\n')
for i, t in enumerate(d.tables, 1):
    out.write('表%d: %d行 x %d列 | 首行: %s\n' % (i, len(t.rows), len(t.columns),
              ' / '.join(c.text[:14] for c in t.rows[0].cells)))

out.write('\n=== 正文字体抽样 ===\n')
seen = 0
for p in paras:
    if p.runs and len(p.text) > 30:
        r = p.runs[0]
        rf = r._element.rPr.rFonts if r._element.rPr is not None else None
        ea = rf.get(qn('w:eastAsia')) if rf is not None else None
        out.write('size=%s bold=%s eastAsia=%s | %s\n' % (r.font.size, r.font.bold, ea, p.text[:26]))
        seen += 1
        if seen >= 5:
            break

out.write('\n=== 字体一致性检查 ===\n')
bad = []
for p in paras:
    for r in p.runs:
        rf = r._element.rPr.rFonts if r._element.rPr is not None else None
        if rf is None or rf.get(qn('w:eastAsia')) is None:
            bad.append(p.text[:30])
            break
out.write('缺东亚字体的段落数: %d\n' % len(bad))

out.write('\n=== 全文文本（供通读） ===\n')
for p in paras:
    if p.text.strip():
        out.write(p.text + '\n')

out.close()
print('OK, 报告已写出')
