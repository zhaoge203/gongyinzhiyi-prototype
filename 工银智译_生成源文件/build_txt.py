# -*- coding: utf-8 -*-
"""导出纯文本版本（供自行排版），表格以制表符对齐呈现"""
import io, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as C

L = []
W = L.append
BAR = '=' * 72
SUB = '-' * 72

W(BAR)
W('第一届香港大学生金融科技创新大赛「工行杯」')
W('参 赛 策 划 案')
W(BAR)
W('')
W(C.TITLE_MAIN)
W(C.TITLE_SUB)
W(C.TITLE_SUB2)
W('')
for k, v in C.TEAM:
    W('%s：%s' % (k, v))
W('')
W('2026 年 10 月')
W('')

seen_tables = 0
for item in C.BLOCKS:
    kind = item[0]
    if kind == 'h1':
        W('')
        W(BAR)
        W(item[1])
        W(BAR)
    elif kind == 'h2':
        W('')
        W(SUB)
        W(item[1])
        W(SUB)
    elif kind == 'h3':
        W('')
        W(item[1])
        W('')
    elif kind == 'p':
        W('　　' + item[1])
    elif kind == 'b':
        W('　　● ' + item[1])
    elif kind == 'n':
        W('　　' + item[1])
    elif kind == 't':
        spec = item[1]
        W('')
        W('【' + spec['caption'] + '】')
        header = spec['header']
        rows = spec['rows']
        ncol = len(header)
        data = [header] + rows

        def dw(s):
            """显示宽度：CJK 与全角字符算 2 列"""
            n = 0
            for ch in str(s):
                n += 2 if (ord(ch) > 0x1100 and (
                    0x2E80 <= ord(ch) <= 0xA4CF or
                    0xAC00 <= ord(ch) <= 0xD7A3 or
                    0xF900 <= ord(ch) <= 0xFAFF or
                    0xFE30 <= ord(ch) <= 0xFE4F or
                    0xFF00 <= ord(ch) <= 0xFF60 or
                    0xFFE0 <= ord(ch) <= 0xFFE6 or
                    0x3000 <= ord(ch) <= 0x303F)) else 1
            return n

        def dtrunc(s, limit):
            s = str(s)
            if dw(s) <= limit:
                return s
            out = ''
            for ch in s:
                if dw(out + ch) > limit - 1:
                    break
                out += ch
            return out + '…'

        # 控制表格总宽，避免在 A4 页面上折行过多
        TOTAL_BUDGET = 116
        MAXCOL = 34
        MINCOL = 8
        nat = [max(dw(r[i]) for r in data) for i in range(ncol)]
        widths = [min(w, MAXCOL) for w in nat]
        overhead = 3 * ncol + 1
        while sum(widths) + overhead > TOTAL_BUDGET:
            # 反复压缩当前最宽的列，直到满足总宽预算
            k = widths.index(max(widths))
            if widths[k] <= MINCOL:
                break
            widths[k] -= 1
        while sum(widths) + overhead > TOTAL_BUDGET:
            k = widths.index(max(widths))
            if widths[k] <= 4:
                break
            widths[k] -= 1

        def wrap(s, limit):
            """按显示宽度折行，返回行列表"""
            s = str(s).replace('\n', ' ')
            lines, cur = [], ''
            for ch in s:
                if dw(cur + ch) > limit:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
            return lines or ['']

        def line(sep='-'):
            return '+' + '+'.join(sep * (w + 2) for w in widths) + '+'

        def fmtrow(r):
            wrapped = [wrap(r[i], widths[i]) for i in range(ncol)]
            height = max(len(c) for c in wrapped)
            out = []
            for li in range(height):
                cells = []
                for i in range(ncol):
                    seg = wrapped[i][li] if li < len(wrapped[i]) else ''
                    cells.append(' ' + seg + ' ' * (widths[i] - dw(seg)) + ' ')
                out.append('|' + '|'.join(cells) + '|')
            return '\n'.join(out)

        W(line('-'))
        W(fmtrow(header))
        W(line('='))
        for r in rows:
            W(fmtrow(r))
            W(line('-'))
        W('')
    elif kind == 'pb':
        pass

out = r'D:\MyStudy\工行杯\工银智译策划案（纯文本版·供排版）.txt'
io.open(out, 'w', encoding='utf-8-sig').write('\n'.join(L))
print('SAVED:', out)
print('行数:', len(L))
