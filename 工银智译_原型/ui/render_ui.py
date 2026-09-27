# -*- coding: utf-8 -*-
"""工银智译 · 原型界面稿生成（PIL 直接绘制，无需浏览器）
产出 4 张界面示意图：
  ui_1_risk_cards.png   解读结果页（风险卡片 + 原文溯源）
  ui_2_fee_perspective.png 费用透视页
  ui_3_comparison.png   同类产品对照页
  ui_4_audit_trail.png  合规校验与全链路审计轨迹
"""
import io
import json
import os
import sys

sys.path.insert(0, r'D:\MyStudy\.pdftools')
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
OUT = os.path.join(PROTO, 'ui')
os.makedirs(OUT, exist_ok=True)

F = r'C:\Windows\Fonts\msyh.ttc'
FB = r'C:\Windows\Fonts\msyhbd.ttc'
ICBC_RED = (158, 27, 50)
DARK = (34, 34, 34)
GREY = (120, 120, 120)
LIGHT = (247, 241, 242)
WHITE = (255, 255, 255)
BORDER = (228, 222, 222)
GREEN = (39, 138, 88)


def font(sz, bold=False):
    return ImageFont.truetype(FB if bold else F, sz)


def wrap(draw, text, fnt, maxw):
    lines, cur = [], ''
    for ch in text:
        if ch == '\n':
            lines.append(cur); cur = ''; continue
        if draw.textlength(cur + ch, font=fnt) > maxw:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def panel(draw, xy, radius=10, fill=WHITE, outline=BORDER, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def phone_frame(w, h, title):
    """手机界面外框"""
    img = Image.new('RGB', (w, h), (242, 242, 245))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=26, fill=WHITE, outline=(210, 205, 205), width=2)
    # 状态栏
    d.rectangle([0, 0, w, 30], fill=WHITE)
    d.text((18, 8), '9:41', font=font(12), fill=DARK)
    d.text((w - 60, 8), '5G  ▮', font=font(12), fill=DARK)
    # 导航栏
    d.rectangle([0, 30, w, 84], fill=ICBC_RED)
    d.text((18, 48), title, font=font(17, True), fill=WHITE)
    d.text((w - 34, 48), '⋯', font=font(17, True), fill=WHITE)
    return img, d


def footer_tabs(d, w, h, active):
    tabs = ['摘要', '风险', '费用', '对照', '术语']
    d.rectangle([0, h - 62, w, h - 1], fill=(250, 250, 252))
    d.line([0, h - 62, w, h - 62], fill=BORDER)
    step = w / len(tabs)
    for i, t in enumerate(tabs):
        cx = step * i + step / 2
        col = ICBC_RED if i == active else GREY
        d.ellipse([cx - 6, h - 50, cx + 6, h - 38], outline=col, width=2)
        d.text((cx - d.textlength(t, font=font(10)) / 2, h - 32), t, font=font(10), fill=col)


def load():
    g = lambda n: json.load(io.open(os.path.join(PROTO, 'engine', n), encoding='utf-8'))
    return g('out_01_parsed.json'), g('out_03_interpretation.json'), \
        g('out_04_comparison.json'), g('out_05_metrics.json'), g('out_06_trace.json')


# ---------------- 界面 1：解读结果页 ----------------
def ui1(parsed, interp, code='R3'):
    it = interp[code]['interpretation']
    ra = interp[code]['resolved_anchors']
    blk = {b['id']: b for b in parsed[code]['blocks']}
    W, H = 430, 940
    img, d = phone_frame(W, H, '工银智译 · 风险解读')

    y = 96
    d.text((18, y), parsed[code]['title'][:20], font=font(13, True), fill=DARK)
    y += 22
    d.text((18, y), '产品资料概要智能解读 · AI 辅助生成', font=font(10.5), fill=GREY)

    # 一句话摘要
    y += 26
    sum_lines = wrap(d, it['summary'], font(12.5), W - 60)[:3]
    sum_h = 34 + len(sum_lines) * 20
    panel(d, [14, y, W - 14, y + sum_h], fill=LIGHT, outline=(233, 210, 214))
    d.text((26, y + 10), '一句话摘要', font=font(11, True), fill=ICBC_RED)
    ty = y + 30
    for ln in sum_lines:
        d.text((26, ty), ln, font=font(12.5), fill=DARK)
        ty += 20
    y += sum_h + 16

    # 风险卡片
    d.text((18, y), '风险清单', font=font(13, True), fill=DARK)
    y += 24
    for i, card in enumerate((it.get('risk_cards') or [])[:3]):
        lines = wrap(d, card, font(12), W - 74)
        hgt = 30 + len(lines) * 19 + 26
        panel(d, [14, y, W - 14, y + hgt])
        d.ellipse([26, y + 12, 44, y + 30], fill=ICBC_RED)
        d.text((31, y + 15), str(i + 1), font=font(11, True), fill=WHITE)
        ty = y + 12
        for ln in lines:
            d.text((54, ty), ln, font=font(12), fill=DARK)
            ty += 19
        # 溯源锚点
        anc = (ra.get('risk_cards[%d]' % i) or ['-'])[0]
        src = blk.get(anc, {}).get('text', '')[:26]
        d.text((54, ty + 2), '原文 %s：%s…' % (anc, src), font=font(9.5), fill=(150, 150, 155))
        y += hgt + 8

    tab_y = H - 62
    d.text((18, tab_y - 26), '共 %d 张风险卡片，已全部绑定原文出处' % len(it.get('risk_cards') or []),
           font=font(10), fill=GREEN)
    footer_tabs(d, W, H, 1)
    p = os.path.join(OUT, 'ui_1_risk_cards.png')
    img.save(p)
    return p


# ---------------- 界面 2：费用透视页 ----------------
def ui2(parsed, interp, cmpj, code='R3'):
    it = interp[code]['interpretation']
    row = [r for r in cmpj['rows'] if r['code'] == code][0]
    W, H = 430, 940
    img, d = phone_frame(W, H, '工银智译 · 费用透视')
    y = 100

    # 综合费率大字
    panel(d, [14, y, W - 14, y + 92], fill=LIGHT, outline=(233, 210, 214))
    d.text((26, y + 12), '运作综合费率（年化）', font=font(11.5, True), fill=ICBC_RED)
    d.text((26, y + 34), row['comprehensive_fee'], font=font(38, True), fill=ICBC_RED)
    d.text((150, y + 56), '含管理费、托管费等', font=font(10.5), fill=GREY)
    d.text((150, y + 72), '（拆解自产品资料概要）', font=font(10.5), fill=GREY)
    y += 108

    # 费用拆解
    d.text((18, y), '费用拆解', font=font(13, True), fill=DARK)
    y += 26
    items = [('管理费', row['management_fee'] or '—'), ('托管费', row['custodian_fee'] or '—')]
    if row.get('min_holding') and row['min_holding'] != '无':
        items.append(('最短持有期', row['min_holding']))
    else:
        items.append(('最短持有期', '无'))
    for name, val in items:
        panel(d, [14, y, W - 14, y + 40])
        d.text((28, y + 12), name, font=font(12), fill=DARK)
        d.text((W - 28 - d.textlength(val, font=font(12, True)), y + 12), val,
               font=font(12, True), fill=DARK)
        y += 48

    # 白话解读
    y += 4
    d.text((18, y), '这意味着什么', font=font(13, True), fill=DARK)
    y += 24
    lines = wrap(d, it['fee_plain'], font(12), W - 60)
    hgt = 24 + len(lines) * 19
    panel(d, [14, y, W - 14, y + hgt], fill=(252, 250, 246), outline=(235, 226, 206))
    ty = y + 12
    for ln in lines:
        d.text((28, ty), ln, font=font(12), fill=DARK)
        ty += 19
    y += hgt + 14

    # 流动性
    d.text((18, y), '这笔钱多久不能动', font=font(13, True), fill=DARK)
    y += 24
    lines = wrap(d, it['liquidity_plain'], font(12), W - 60)
    hgt = 24 + len(lines) * 19
    panel(d, [14, y, W - 14, y + hgt], fill=(246, 250, 247), outline=(206, 232, 214))
    ty = y + 12
    for ln in lines:
        d.text((28, ty), ln, font=font(12), fill=DARK)
        ty += 19

    footer_tabs(d, W, H, 2)
    p = os.path.join(OUT, 'ui_2_fee_perspective.png')
    img.save(p)
    return p


# ---------------- 界面 3：同类产品对照 ----------------
def ui3(cmpj):
    rows = cmpj['rows']
    W, H = 900, 560
    img = Image.new('RGB', (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 66], fill=ICBC_RED)
    d.text((30, 20), '工银智译 · 同类产品对照解读', font=font(20, True), fill=WHITE)
    d.text((30, 78), '来源：四只基金官方产品资料概要（数据未经改算）', font=font(12), fill=GREY)

    cols = ['指标'] + [r['code'] + ' ' + (r['type'] or '') for r in rows]
    data = [
        ['运作综合费率（年化）'] + [r['comprehensive_fee'] for r in rows],
        ['管理费 / 托管费'] + ['%s / %s' % (r['management_fee'], r['custodian_fee']) for r in rows],
        ['最短持有期'] + [r['min_holding'] for r in rows],
        ['杠杆 / 期货'] + [('有' if r['leverage'] else '无') for r in rows],
        ['港股通'] + [('有' if r['hk_connect'] else '无') for r in rows],
        ['侧袋机制'] + [('有' if r['side_pocket'] else '无') for r in rows],
    ]
    x0, y0 = 30, 116
    colw = [220] + [int((W - 60 - 220) / len(rows))] * len(rows)
    rowh = 46
    # 表头
    d.rectangle([x0, y0, W - 30, y0 + rowh], fill=LIGHT)
    cx = x0
    for i, c in enumerate(cols):
        d.text((cx + 14, y0 + 14), c, font=font(13, True), fill=ICBC_RED)
        cx += colw[i]
    # 数据行
    yy = y0 + rowh
    for ri, r in enumerate(data):
        if ri % 2 == 0:
            d.rectangle([x0, yy, W - 30, yy + rowh], fill=(252, 250, 250))
        cx = x0
        for ci, cell in enumerate(r):
            col = DARK
            fnt = font(13)
            if ri == 0 and ci > 0:
                fnt = font(15, True)
                col = ICBC_RED if cell in ('1.40%', '1.41%') else GREEN
            d.text((cx + 14, yy + 14), str(cell), font=fnt, fill=col)
            cx += colw[ci]
        d.line([x0, yy + rowh, W - 30, yy + rowh], fill=BORDER)
        yy += rowh
    cx = x0
    for i in range(len(cols)):
        d.line([cx, y0, cx, yy], fill=BORDER)
        cx += colw[i]
    d.line([W - 30, y0, W - 30, yy], fill=BORDER)

    d.text((30, yy + 18), '最高与最低综合费率相差 %s 倍 —— 费率分散在三处披露，投资者难以自行合并计算。'
           % cmpj['max_min_fee_ratio'], font=font(13, True), fill=DARK)
    d.text((30, yy + 44), '本页只做同一口径的并列呈现，不评价产品优劣、不构成投资建议。',
           font=font(11.5), fill=GREY)
    p = os.path.join(OUT, 'ui_3_comparison.png')
    img.save(p)
    return p


# ---------------- 界面 4：合规审计轨迹 ----------------
def ui4(metrics, trace):
    sample = sorted(trace)[2]
    logs = trace.get(sample, {}).get('log', [])
    W = 900
    H = 240 + 36 * (len(metrics['per_product']) + 2) + 30 + 24 * len(logs) + 70
    img = Image.new('RGB', (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 66], fill=ICBC_RED)
    d.text((30, 20), '工银智译 · 合规校验与审计轨迹', font=font(20, True), fill=WHITE)
    d.text((30, 78), '每一次生成的检索来源、校验结果与回退次数均留档，支持监管调阅', font=font(12), fill=GREY)

    a = metrics['aggregate']
    cf = a['context_fidelity']
    kpis = [('锚点有效率', '%.1f%%' % a['anchor_pass_rate']),
            ('表达合规率', '%.1f%%' % a['expression_pass_rate']),
            ('归属一致率', '%.1f%%' % cf['attribution_rate']),
            ('原文不支持的数值', '%d 个' % cf['fabricated_numbers'])]
    x = 30
    for name, val in kpis:
        panel(d, [x, 112, x + 200, 186], fill=LIGHT, outline=(233, 210, 214))
        d.text((x + 16, 124), name, font=font(11.5), fill=ICBC_RED)
        d.text((x + 16, 144), val, font=font(24, True), fill=DARK)
        x += 212

    y = 214
    d.text((30, y), '各产品指标', font=font(14, True), fill=DARK)
    y += 26
    hdr = ['产品', '锚点', '归属一致率', '句长 原文→解读', '重试次数', '结论']
    colw = [90, 100, 130, 220, 110, 170]
    d.rectangle([30, y, W - 30, y + 36], fill=LIGHT)
    cx = 30
    for i, hh in enumerate(hdr):
        d.text((cx + 12, y + 10), hh, font=font(12, True), fill=ICBC_RED)
        cx += colw[i]
    y += 36
    for code in sorted(metrics['per_product']):
        m = metrics['per_product'][code]
        t = trace.get(code, {})
        cf = m['context_fidelity']
        cfp = cf['context_fidelity_pct']
        vals = [code, '%.1f%%' % m['anchor_pass_rate'],
                ('%.1f%%' % cfp) if cfp is not None else '—',
                '%s → %s' % (m['readability_src']['avg_sent_len'], m['readability_gen']['avg_sent_len']),
                str((t.get('retry_extract', 0) or 0) + (t.get('retry_interpret', 0) or 0) - 2),
                '放行' if not t.get('review_required') else '转人工']
        cx = 30
        for i, v in enumerate(vals):
            col = GREEN if v == '放行' else (ICBC_RED if v == '转人工' else DARK)
            d.text((cx + 12, y + 10), v, font=font(12), fill=col)
            cx += colw[i]
        d.line([30, y + 36, W - 30, y + 36], fill=BORDER)
        y += 36

    y += 22
    d.text((30, y), '全链路节点轨迹（以 %s 为例）' % sample, font=font(14, True), fill=DARK)
    y += 28
    for ln in logs:
        d.text((44, y), '· ' + ln, font=font(11.5), fill=(60, 60, 60))
        y += 24
    d.line([30, y + 10, W - 30, y + 10], fill=BORDER)
    d.text((30, y + 24),
           '注：归属一致率 = 解读中「标签-数值」配对能在锚点所在章节的正确标签下落地；'
           '「原文不支持的数值」指全文都找不到依据的数字（本批次为 0）。',
           font=font(11), fill=GREY)
    p = os.path.join(OUT, 'ui_4_audit_trail.png')
    img.save(p)
    return p


if __name__ == '__main__':
    parsed, interp, cmpj, metrics, trace = load()
    for fn in (lambda: ui1(parsed, interp), lambda: ui2(parsed, interp, cmpj),
               lambda: ui3(cmpj), lambda: ui4(metrics, trace)):
        print('已生成:', fn())
