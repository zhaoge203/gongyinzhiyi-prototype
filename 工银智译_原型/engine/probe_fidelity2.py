# -*- coding: utf-8 -*-
"""验证重构后的保真度指标：能否拦住语义错配，且不误伤真实输出"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity as F

parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
interp = json.load(io.open(os.path.join(HERE, 'out_03_interpretation.json'), encoding='utf-8'))


def old_fidelity(gen, src):
    """旧指标：数值是否在原文任意位置出现过"""
    s = set(re.findall(r'\d+(?:\.\d+)?%', src))
    g = set(re.findall(r'\d+(?:\.\d+)?%', gen))
    bad = sorted(p for p in g if p not in s)
    return round((1 - len(bad) / max(len(g), 1)) * 100, 1)


def new_fidelity(text, anchors, code):
    blocks = parsed[code]['blocks']
    idx = F.build_index(parsed[code])
    ft = '\n'.join(b['text'] for b in blocks)
    ok, mis, unsup, unt = F.check_text(text, anchors, blocks, idx, ft)
    n = len(ok) + len(mis) + len(unsup)
    pct = round(len(ok) / n * 100, 1) if n else None
    return pct, ok, mis, unsup


print('=' * 84)
print('A. 语义错配样本：旧指标 vs 新指标')
print('=' * 84)
cases = [
    ('P03', '管理费/托管费 归属对调', '管理费0.2%，托管费1.2%。', ['B077', 'B078'], '应拦截'),
    ('P03', '申购费说成赎回费', '赎回时收您1.5%的赎回费。', ['B066', 'B072'], '应拦截'),
    ('P03', '年化综合费率说成月费率', '每月运作综合费率1.40%。', ['B093'], '应拦截（同值不同义）'),
    ('P01', '管理费/销售服务费 对调', '管理费0.25%，销售服务费0.15%。', ['B057', 'B060'], '应拦截'),
    ('P03', '正确的解读', '管理费1.2%，托管费0.2%。', ['B077', 'B078'], '应通过'),
    ('P01', '正确的解读', '管理费0.15%，托管费0.05%。', ['B057', 'B058'], '应通过'),
]
for code, name, text, anchors, expect in cases:
    src = '\n'.join(b['text'] for b in parsed[code]['blocks'])
    of = old_fidelity(text, src)
    nf, ok, mis, unsup = new_fidelity(text, anchors, code)
    verdict = '拦截' if (mis or unsup) else '通过'
    flag = 'OK' if (verdict == '拦截') == expect.startswith('应拦截') else '!! 与预期不符'
    print('  %-22s %-16s 旧=%5.1f%%  新=%5s%%  %s  [%s]'
          % (name, expect, of, nf, verdict, flag))
    if mis:
        print('        跨处引用: %s' % mis)

print()
print('=' * 84)
print('B. 真实生成输出的上下文一致性（新指标，四只产品）')
print('=' * 84)
agg_ok = agg_mis = agg_uns = 0
codes = [c for c in sorted(interp) if 'interpretation' in interp[c]]
for code in codes:
    r = F.evaluate(interp[code], parsed[code])
    agg_ok += r['grounded_pairs']
    agg_mis += len(r['misattributed_pairs'])
    agg_uns += len(r['unsupported_pairs'])
    print('%s  标签-数值对 %-3d 落地 %-3d 跨处引用 %-2d 原文不支持 %-2d 一致性 %s%%'
          % (code, r['total_labeled_pairs'], r['grounded_pairs'],
             len(r['misattributed_pairs']), len(r['unsupported_pairs']),
             r['context_fidelity_pct']))
    for u in r['misattributed_pairs'][:3]:
        print('      [跨处引用] %s: %s=%s' % (u['field'], u['label'], u['value']))
    for u in r['unsupported_pairs'][:3]:
        print('      [原文不支持] %s: %s=%s' % (u['field'], u['label'], u['value']))
    if r['untagged_numbers']:
        vals = sorted({u['value'] for u in r['untagged_numbers']})
        print('      [未挂标签的数值，另有 %d 处] %s' % (len(r['untagged_numbers']), vals))

n = agg_ok + agg_mis + agg_uns
print('\n汇总：标签-数值对共 %d 个 → 落地 %d，跨处引用 %d，原文不支持 %d'
      % (n, agg_ok, agg_mis, agg_uns))
print('      上下文一致率 %.1f%%' % (agg_ok / max(n, 1) * 100))
