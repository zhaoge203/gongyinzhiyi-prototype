# -*- coding: utf-8 -*-
"""生成《工银智译——金融产品风险揭示书智能解读平台》参赛策划案 .docx"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import content as C

IMG_DIR = r'D:\MyStudy\工银智译_原型\ui'

CN_BODY = "宋体"
CN_HEAD = "黑体"
EN_FONT = "Times New Roman"
ACCENT = RGBColor(0x9E, 0x1B, 0x32)   # 工行红
GREY = RGBColor(0x59, 0x59, 0x59)


def set_run(run, size=12, bold=False, cn=CN_BODY, color=None, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = EN_FONT
    run._element.rPr.rFonts.set(qn('w:eastAsia'), cn)
    run._element.rPr.rFonts.set(qn('w:ascii'), EN_FONT)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), EN_FONT)
    if color is not None:
        run.font.color.rgb = color


def style_doc(doc):
    st = doc.styles['Normal']
    st.font.name = EN_FONT
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), CN_BODY)
    pf = st.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    for i in range(1, 5):
        s = doc.styles['Heading %d' % i]
        s.font.name = EN_FONT
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.element.rPr.rFonts.set(qn('w:eastAsia'), CN_HEAD)


def para(doc, text, size=12, bold=False, cn=CN_BODY, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         indent=True, before=0, after=0, color=None, line=1.5):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if indent:
        pf.first_line_indent = Pt(size * 2)
    set_run(p.add_run(text), size=size, bold=bold, cn=cn, color=color)
    return p


def h(doc, text, level):
    sizes = {1: 16, 2: 14, 3: 12.5}
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.space_before = Pt(14 if level == 1 else 10)
    pf.space_after = Pt(7 if level == 1 else 5)
    pf.line_spacing = 1.3
    pf.keep_with_next = True
    set_run(p.add_run(text), size=sizes.get(level, 12), bold=True, cn=CN_HEAD,
            color=ACCENT if level == 1 else RGBColor(0, 0, 0))
    # 让标题进入 Word 导航窗格 / 目录
    p.style = doc.styles['Heading %d' % level]
    for r in p.runs:
        set_run(r, size=sizes.get(level, 12), bold=True, cn=CN_HEAD,
                color=ACCENT if level == 1 else RGBColor(0, 0, 0))
    return p


def bullet(doc, text, size=12):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.left_indent = Pt(size * 2)
    pf.first_line_indent = Pt(-size)
    pf.space_after = Pt(0)
    set_run(p.add_run("● " + text), size=size)
    return p


def numbered(doc, text, size=11):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.4
    pf.left_indent = Pt(size * 1.9)
    pf.first_line_indent = Pt(-size * 1.9)
    set_run(p.add_run(text), size=size)
    return p


def caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.space_before = Pt(8)
    pf.space_after = Pt(3)
    pf.line_spacing = 1.2
    pf.keep_with_next = True
    set_run(p.add_run(text), size=10.5, bold=True, cn=CN_HEAD, color=GREY)
    return p


def add_table(doc, spec):
    header = spec["header"]
    rows = spec["rows"]
    tbl = doc.add_table(rows=1, cols=len(header))
    tbl.style = 'Table Grid'
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = True
    # 固定版式，避免 Word 自动重排撑破页面
    tblPr = tbl._tbl.tblPr
    layout = OxmlElement('w:tblLayout')
    layout.set(qn('w:type'), 'fixed')
    tblPr.append(layout)
    if spec.get("widths"):
        total = sum(spec["widths"])
        for row in tbl.rows:
            for i, w in enumerate(spec["widths"]):
                row.cells[i].width = Cm(w)
    hdr = tbl.rows[0].cells
    for i, txt in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(1)
        set_run(p.add_run(txt), size=10.5, bold=True, cn=CN_HEAD, color=RGBColor(0xFF, 0xFF, 0xFF))
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:fill'), '9E1B32')
        hdr[i]._tc.get_or_add_tcPr().append(shd)
    for ri, r in enumerate(rows):
        cells = tbl.add_row().cells
        for i, txt in enumerate(r):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            set_run(p.add_run(txt), size=10)
            if ri % 2 == 1:
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:fill'), 'F7F1F2')
                cells[i]._tc.get_or_add_tcPr().append(shd)
    if spec.get("widths"):
        for row in tbl.rows:
            for i, w in enumerate(spec["widths"]):
                row.cells[i].width = Cm(w)
    # 表头跨页重复
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'true')
    trPr.append(th)
    # 表后留白
    g = doc.add_paragraph()
    g.paragraph_format.space_after = Pt(6)
    g.paragraph_format.line_spacing = 1.0
    return tbl


def figure(doc, path, caption_text, width_cm=15.4):
    """插入界面稿图片，居中 + 题注"""
    if not os.path.exists(path):
        print('!! 缺少图片:', path)
        return None
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    img_run = p.add_run()
    set_run(img_run, size=1)          # 空 run 也需指定东亚字体，避免字体回退
    img_run.add_picture(path, width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    cap.paragraph_format.line_spacing = 1.2
    set_run(cap.add_run(caption_text), size=10.5, bold=True, cn=CN_HEAD, color=GREY)
    return p


def page_break(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    set_run(r, size=12)
    r.add_break(WD_BREAK.PAGE)
    return p


def add_page_numbers(section):
    """页脚居中页码"""
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    fld1 = OxmlElement('w:fldChar'); fld1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = ' PAGE '
    fld2 = OxmlElement('w:fldChar'); fld2.set(qn('w:fldCharType'), 'end')
    r._r.append(fld1); r._r.append(instr); r._r.append(fld2)
    set_run(r, size=10.5, color=GREY)


def build():
    doc = Document()
    style_doc(doc)

    sec = doc.sections[0]
    sec.top_margin = Cm(2.6); sec.bottom_margin = Cm(2.4)
    sec.left_margin = Cm(3.0); sec.right_margin = Cm(2.6)
    add_page_numbers(sec)

    # ---------------- 封面 ----------------
    for _ in range(2):
        p = doc.add_paragraph(); p.paragraph_format.line_spacing = 1.0
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    set_run(p.add_run("第一届香港大学生金融科技创新大赛"), size=16, bold=True, cn=CN_HEAD)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(28)
    set_run(p.add_run("「工行杯」"), size=17, bold=True, cn=CN_HEAD, color=ACCENT)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    set_run(p.add_run("参 赛 策 划 案"), size=15, bold=True, cn=CN_HEAD, color=GREY)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    set_run(p.add_run(C.TITLE_MAIN), size=40, bold=True, cn=CN_HEAD, color=ACCENT)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    set_run(p.add_run(C.TITLE_SUB), size=15, bold=True, cn=CN_HEAD)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(44)
    set_run(p.add_run(C.TITLE_SUB2), size=12.5, cn=CN_BODY, color=GREY)

    # 信息表
    t = doc.add_table(rows=0, cols=2)
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in C.TEAM:
        cells = t.add_row().cells
        cells[0].width = Cm(3.4); cells[1].width = Cm(9.6)
        for cell, txt, bold, al in ((cells[0], k, True, WD_ALIGN_PARAGRAPH.CENTER),
                                    (cells[1], v, False, WD_ALIGN_PARAGRAPH.LEFT)):
            cell.text = ""
            pp = cell.paragraphs[0]
            pp.alignment = al
            pp.paragraph_format.line_spacing = 1.4
            pp.paragraph_format.space_before = Pt(3)
            pp.paragraph_format.space_after = Pt(3)
            set_run(pp.add_run(txt), size=12, bold=bold, cn=CN_HEAD if bold else CN_BODY)
            if bold:
                shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:fill'), 'F7F1F2')
                cell._tc.get_or_add_tcPr().append(shd)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    set_run(p.add_run("2026 年 10 月"), size=12.5, cn=CN_BODY, color=GREY)

    page_break(doc)

    # ---------------- 目录 ----------------
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(16)
    set_run(p.add_run("目　　录"), size=18, bold=True, cn=CN_HEAD, color=ACCENT)

    toc_p = doc.add_paragraph()
    r = toc_p.add_run()
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve')
    it.text = r' TOC \o "1-3" \h \z \u '
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'separate')
    t_ = OxmlElement('w:t'); t_.text = "请在 Word 中按 Ctrl+A 后按 F9 更新目录域。"
    f3 = OxmlElement('w:fldChar'); f3.set(qn('w:fldCharType'), 'end')
    r._r.append(f1); r._r.append(it); r._r.append(f2); r._r.append(t_); r._r.append(f3)
    set_run(r, size=11.5)

    page_break(doc)

    # ---------------- 正文 ----------------
    for item in C.BLOCKS:
        kind = item[0]
        if kind == 'h1':
            h(doc, item[1], 1)
        elif kind == 'h2':
            h(doc, item[1], 2)
        elif kind == 'h3':
            h(doc, item[1], 3)
        elif kind == 'p':
            para(doc, item[1])
        elif kind == 'b':
            bullet(doc, item[1])
        elif kind == 'n':
            numbered(doc, item[1])
        elif kind == 'cap':
            caption(doc, item[1])
        elif kind == 'fig':
            fname, cap_text, wcm = item[1]
            figure(doc, os.path.join(IMG_DIR, fname), cap_text, wcm)
        elif kind == 't':
            spec = item[1]
            caption(doc, spec["caption"])
            add_table(doc, spec)
        elif kind == 'pb':
            page_break(doc)
        else:
            raise ValueError('unknown block: ' + kind)

    out = r'D:\MyStudy\工行杯\工银智译——金融产品资料概要智能解读平台策划案（包家瑞、卢欣烨）.docx'
    doc.save(out)
    return out


if __name__ == '__main__':
    path = build()
    print('SAVED:', path)
    # 统计
    d = Document(path)
    chars = sum(len(p.text) for p in d.paragraphs)
    tchars = 0
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                tchars += len(c.text)
    print('段落数:', len(d.paragraphs), '表格数:', len(d.tables))
    print('正文字符数(不含表格):', chars, '表格字符数:', tchars, '合计:', chars + tchars)
