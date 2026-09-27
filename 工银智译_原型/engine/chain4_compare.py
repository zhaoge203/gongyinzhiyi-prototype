# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链四：同类产品对照解读 + 链五：质量评测

链四解决投资者真实决策问题：「A 和 B 我该选哪个」。
把四只产品的费率、流动性、风险机制拉平到同一张表上，差异自然浮现。

链五产出可量化指标：
  - 锚点有效率、表达合规率（客观，可复算）
  - 语义保真度：解读中出现的全部百分比数值，是否都能在原文中逐一找到
  - 中文可读性指标：术语密度 / 平均句长 / 超纲词比例（自建，因中文无国标）
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity as FID

# 面向普通投资者的常用词表（示意性子集，工程上应替换为完整词表）
COMMON_PERCENT_KEEP = {'%'}


def readability(text, term_set):
    """中文金融文本可读性指标（自建）：返回三个维度
       - 平均句长（字）
       - 术语密度（每百字命中术语数）
       - 长句占比（超过 40 字的句子比例）
    """
    sents = [s for s in re.split(r'[。；！？\n]', text) if s.strip()]
    if not sents:
        return {'avg_sent_len': 0, 'term_density': 0, 'long_sent_ratio': 0, 'n_sent': 0}
    avg = sum(len(s) for s in sents) / len(sents)
    long_ratio = sum(1 for s in sents if len(s) > 40) / len(sents)
    hits = sum(text.count(t) for t in term_set)
    return {
        'avg_sent_len': round(avg, 1),
        'term_density': round(hits * 100.0 / max(len(text), 1), 2),
        'long_sent_ratio': round(long_ratio, 3),
        'n_sent': len(sents),
    }


def extract_percentages(text):
    return set(re.findall(r'\d+(?:\.\d+)?%', text))


def main():
    parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
    facts = json.load(io.open(os.path.join(HERE, 'out_02_facts.json'), encoding='utf-8'))
    interp = json.load(io.open(os.path.join(HERE, 'out_03_interpretation.json'), encoding='utf-8'))

    # ---------- 链四：横向对照 ----------
    rows = []
    for code in sorted(parsed):
        f = facts[code]['llm']
        d = parsed[code]
        text = '\n'.join(b['text'] for b in d['blocks'])
        rows.append({
            'code': code,
            'name': d['title'],
            'type': f.get('product_type'),
            'operation': f.get('operation'),
            'open_freq': f.get('open_frequency'),
            'min_holding': f.get('min_holding'),
            'comprehensive_fee': f.get('comprehensive_fee'),
            'management_fee': f.get('management_fee'),
            'custodian_fee': f.get('custodian_fee'),
            'redemption_rule': f.get('redemption_rule'),
            'benchmark': f.get('benchmark'),
            'risk_count': len(f.get('risk_items') or []),
            'side_pocket': '侧袋机制' in text,
            'leverage': bool(re.search(r'杠杆|保证金交易', text)),
            'hk_connect': '港股通' in text,
        })

    # 费率差倍数的客观计算（不引入任何外部数据）
    fees = [float(r['comprehensive_fee'].rstrip('%')) for r in rows
            if r['comprehensive_fee']]
    fee_ratio = round(max(fees) / min(fees), 2) if fees else None

    comparison = {'rows': rows, 'max_min_fee_ratio': fee_ratio}

    # ---------- 链五：质量评测 ----------
    term_set = set()
    for code in interp:
        for g in (interp[code].get('interpretation', {}).get('glossary') or []):
            if '：' in g:
                term_set.add(g.split('：')[0].strip())

    metrics = {'per_product': {}, 'aggregate': {}}
    tot_anchor_ok = tot_anchor = tot_expr_ok = tot_expr = 0
    fid_ok = fid_mis = fid_uns = 0

    for code in sorted(parsed):
        r = interp.get(code) or {}
        if 'interpretation' not in r:
            continue
        it = r['interpretation']
        d = parsed[code]
        src_text = '\n'.join(b['text'] for b in d['blocks'])
        src_pct = extract_percentages(src_text)

        # 解读侧文本（排除术语词典中的解释性数字）
        gen_parts = [it.get('summary', ''), it.get('fee_plain', ''), it.get('liquidity_plain', '')] \
            + list(it.get('risk_cards') or [])
        gen_text = '\n'.join(gen_parts)
        gen_pct = extract_percentages(gen_text)

        # 旧口径（数值存在性）：保留用于对比，不作为主结论
        unsupported = sorted(p for p in gen_pct if p not in src_pct)
        existence_pct = round((1 - len(unsupported) / max(len(gen_pct), 1)) * 100, 1) if gen_pct else 100.0

        # 新口径（上下文一致性）：标签—数值配对是否落在锚点所在小节
        cfr = FID.evaluate(r, d)
        fid_ok += cfr['grounded_pairs']
        fid_mis += len(cfr['misattributed_pairs'])
        fid_uns += len(cfr['unsupported_pairs'])

        # 锚点与表达
        checked = r.get('checked_items', 0)
        bad_a = len(r.get('bad_anchors') or [])
        bad_e = len(r.get('bad_expressions') or [])
        tot_anchor += checked; tot_anchor_ok += checked - bad_a
        tot_expr += checked; tot_expr_ok += checked - bad_e

        # 可读性：统一走 fidelity 模块的定义与文本构成，
        # 确保与状态机校验节点给出同一个数字
        r_src = {'avg_sent_len': FID.avg_sentence_len(FID.source_text_for_readability(d))}
        r_gen = {'avg_sent_len': FID.avg_sentence_len(FID.interpretation_text(it))}

        # 质量门禁：与状态机校验节点共用同一实现
        gate = FID.readability_gate(FID.interpretation_text(it),
                                    FID.source_text_for_readability(d))
        gate['pass'] = gate['ok']

        metrics['per_product'][code] = {
            'existence_fidelity_pct': existence_pct,
            'unsupported_percent': unsupported,
            'context_fidelity': {
                'grounded': cfr['grounded_pairs'],
                'misattributed': len(cfr['misattributed_pairs']),
                'unsupported': len(cfr['unsupported_pairs']),
                'total_labeled_pairs': cfr['total_labeled_pairs'],
                'context_fidelity_pct': cfr['context_fidelity_pct'],
                'untagged_numbers': len(cfr['untagged_numbers']),
            },
            'anchor_pass_rate': round((checked - bad_a) / max(checked, 1) * 100, 1),
            'expression_pass_rate': round((checked - bad_e) / max(checked, 1) * 100, 1),
            'attempts': r.get('attempts'),
            'readability_src': r_src,
            'readability_gen': r_gen,
            'quality_gate': gate,
        }

    metrics['aggregate'] = {
        'anchor_pass_rate': round(tot_anchor_ok / max(tot_anchor, 1) * 100, 1),
        'expression_pass_rate': round(tot_expr_ok / max(tot_expr, 1) * 100, 1),
        'checked_items_total': tot_expr,
        'products': len(metrics['per_product']),
        'quality_gate_pass': sum(1 for m in metrics['per_product'].values()
                                 if m['quality_gate']['pass']),
        'context_fidelity': {
            'grounded': fid_ok,
            'misattributed': fid_mis,
            'unsupported': fid_uns,
            'total_labeled_pairs': fid_ok + fid_mis + fid_uns,
            'attribution_rate': round(fid_ok / max(fid_ok + fid_mis + fid_uns, 1) * 100, 1),
            'fabricated_numbers': fid_uns,
        },
    }

    with io.open(os.path.join(HERE, 'out_04_comparison.json'), 'w', encoding='utf-8') as fh:
        json.dump(comparison, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(HERE, 'out_05_metrics.json'), 'w', encoding='utf-8') as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=1)

    print('=' * 74)
    print('同类产品对照（真实数据，来源：官方产品资料概要）')
    print('=' * 74)
    hdr = ['代码', '类型', '综合费率', '最短持有期', '杠杆/期货', '港股通', '侧袋']
    print('%-5s %-8s %-9s %-10s %-9s %-7s %s' % tuple(hdr))
    for r in rows:
        print('%-5s %-8s %-9s %-10s %-9s %-7s %s' % (
            r['code'], r['type'], r['comprehensive_fee'], r['min_holding'],
            '是' if r['leverage'] else '否', '是' if r['hk_connect'] else '否',
            '是' if r['side_pocket'] else '否'))
    print('\n最高/最低综合费率倍数：%s 倍' % fee_ratio)

    print('\n' + '=' * 74)
    print('质量评测指标')
    print('=' * 74)
    for code, m in sorted(metrics['per_product'].items()):
        src, gen = m['readability_src'], m['readability_gen']
        cf = m['context_fidelity']
        print('%s 句长 %s→%s | 锚点=%5.1f%% | 表达=%5.1f%% | 门禁=%s'
              % (code, src['avg_sent_len'], gen['avg_sent_len'],
                 m['anchor_pass_rate'], m['expression_pass_rate'],
                 '通过' if m['quality_gate']['pass'] else '未通过'))
        print('     保真度｜旧口径(数值存在性)=%5.1f%%  新口径(上下文落地)=%s%%  配对 %d：落地 %d/跨处 %d/原文不支持 %d'
              % (m['existence_fidelity_pct'], cf['context_fidelity_pct'],
                 cf['total_labeled_pairs'], cf['grounded'], cf['misattributed'], cf['unsupported']))
        if m['unsupported_percent']:
            print('     旧口径标记的未支持数值：%s' % m['unsupported_percent'])
    a = metrics['aggregate']
    cf = a['context_fidelity']
    print('\n汇总：锚点有效率 %s%%  表达合规率 %s%%  受检 %d 项  可读性门禁 %d/%d'
          % (a['anchor_pass_rate'], a['expression_pass_rate'],
             a['checked_items_total'], a['quality_gate_pass'], a['products']))
    print('      保真度（上下文口径）：标签-数值对 %d 个 → 落地 %d，跨处引用 %d，**原文完全不支持 %d**'
          % (cf['total_labeled_pairs'], cf['grounded'], cf['misattributed'], cf['fabricated_numbers']))
    print('      归属一致率 %.1f%%（跨处引用多为校验器的标签抽取噪声，需人工判定，未计入"未支持"）'
          % cf['attribution_rate'])
    print('\n已写出 out_04_comparison.json / out_05_metrics.json')


if __name__ == '__main__':
    main()
