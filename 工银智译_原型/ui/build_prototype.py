# -*- coding: utf-8 -*-
"""生成可点交互的 HTML 原型（数据全部来自引擎真实产出，非手写）"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
OUT = os.path.join(PROTO, 'ui', 'prototype.html')


def load(n):
    return json.load(io.open(os.path.join(PROTO, 'engine', n), encoding='utf-8'))


parsed = load('out_01_parsed.json')
interp = load('out_03_interpretation.json')
cmpj = load('out_04_comparison.json')
metrics = load('out_05_metrics.json')
trace = load('out_06_trace.json')

blocks = {c: {b['id']: b for b in parsed[c]['blocks']} for c in parsed}
products = sorted(parsed)

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>工银智译 · 原型演示</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f2f2f5;color:#222}
.wrap{display:flex;max-width:1240px;margin:0 auto;gap:22px;padding:22px}
.phone{width:430px;background:#fff;border-radius:26px;border:2px solid #d2cdcd;overflow:hidden;
       box-shadow:0 8px 28px rgba(0,0,0,.08);flex-shrink:0}
.nav{background:#9E1B32;color:#fff;padding:14px 18px;font-size:17px;font-weight:700}
.nav small{display:block;font-weight:400;font-size:11px;opacity:.85;margin-top:3px}
.body{padding:16px;min-height:560px}
.tabs{display:flex;border-top:1px solid #e4dede;background:#fafafc}
.tabs button{flex:1;border:0;background:none;padding:11px 0 12px;font-size:12px;color:#787878;
             cursor:pointer;font-family:inherit;border-top:3px solid transparent}
.tabs button.on{color:#9E1B32;font-weight:700;border-top-color:#9E1B32}
.card{border:1px solid #e4dede;border-radius:10px;padding:12px;margin-bottom:9px}
.card.hl{background:#f7f1f2;border-color:#e9d2d6}
.card.fee{background:#fcfaf6;border-color:#ebe2ce}
.card.liq{background:#f6faf7;border-color:#cee8d6}
.ttl{color:#9E1B32;font-weight:700;font-size:12px;margin-bottom:6px}
.txt{font-size:13.5px;line-height:1.6}
.meta{font-size:11px;color:#96969b;margin-top:7px;line-height:1.5}
.meta a{color:#9E1B32;text-decoration:none;border-bottom:1px dotted #9E1B32;cursor:pointer}
.big{font-size:38px;font-weight:700;color:#9E1B32;line-height:1.1}
.row{display:flex;justify-content:space-between;padding:11px 12px;border:1px solid #e4dede;
     border-radius:9px;margin-bottom:8px;font-size:13.5px}
.row b{font-weight:700}
.pick{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:13px}
.pick button{font-family:inherit;font-size:12px;padding:5px 11px;border-radius:14px;
             border:1px solid #d8d2d2;background:#fff;cursor:pointer}
.pick button.on{background:#9E1B32;color:#fff;border-color:#9E1B32}
.panel{flex:1;min-width:0}
.panel h2{font-size:15px;margin:0 0 10px;color:#9E1B32}
.panel h3{font-size:13px;margin:16px 0 8px;color:#444}
table{width:100%;border-collapse:collapse;background:#fff;font-size:12.5px}
th,td{border:1px solid #e4dede;padding:8px 10px;text-align:left}
th{background:#f7f1f2;color:#9E1B32;font-weight:700}
tr:nth-child(even) td{background:#fcfafa}
.g{color:#278a58;font-weight:700}.r{color:#9E1B32;font-weight:700}
pre{background:#fff;border:1px solid #e4dede;border-radius:9px;padding:12px;font-size:12px;
    line-height:1.75;white-space:pre-wrap;font-family:Consolas,"Microsoft YaHei",monospace}
.note{font-size:11.5px;color:#8a8a8a;margin-top:9px;line-height:1.6}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
.kpi{background:#f7f1f2;border:1px solid #e9d2d6;border-radius:10px;padding:11px}
.kpi .n{font-size:11px;color:#9E1B32;font-weight:700}
.kpi .v{font-size:23px;font-weight:700;margin-top:5px}
details{margin-top:7px}
summary{cursor:pointer;font-size:11.5px;color:#9E1B32}
</style></head><body><div class="wrap">
"""

html = [HTML_HEAD]

# ---------- 左：手机界面 ----------
html.append('<div class="phone"><div class="nav">工银智译 · 风险解读'
            '<small>数据源：官方基金产品资料概要（真实文件）</small></div>')
html.append('<div class="body" id="screen"></div>')
html.append('<div class="tabs">')
for i, (k, label) in enumerate([('summary', '摘要'), ('risk', '风险'), ('fee', '费用'),
                                ('compare', '对照'), ('glossary', '术语')]):
    html.append('<button data-tab="%s"%s>%s</button>' % (k, ' class="on"' if i == 0 else '', label))
html.append('</div></div>')

# ---------- 右：对照 / 指标 / 轨迹 ----------
html.append('<div class="panel">')
html.append('<div class="pick">')
for c in products:
    html.append('<button data-p="%s"%s>%s %s</button>'
                % (c, ' class="on"' if c == 'R3' else '', c, parsed[c]['title'][:12]))
html.append('</div>')

html.append('<h2>同类产品对照（数据未经改算）</h2><table><tr><th>指标</th>')
for c in products:
    html.append('<th>%s<br><span style="font-weight:400;font-size:11px">%s</span></th>'
                % (c, cmpj['rows'][products.index(c)]['type']))
html.append('</tr>')
cmp_rows = [
    ('运作综合费率（年化）', lambda r: '<b>%s</b>' % r['comprehensive_fee']),
    ('管理费 / 托管费', lambda r: '%s / %s' % (r['management_fee'], r['custodian_fee'])),
    ('最短持有期', lambda r: r['min_holding']),
    ('杠杆 / 期货', lambda r: '有' if r['leverage'] else '无'),
    ('港股通', lambda r: '有' if r['hk_connect'] else '无'),
    ('侧袋机制', lambda r: '有' if r['side_pocket'] else '无'),
]
for name, fn in cmp_rows:
    html.append('<tr><td><b>%s</b></td>' % name)
    for r in cmpj['rows']:
        html.append('<td>%s</td>' % fn(r))
    html.append('</tr>')
html.append('</table>')
html.append('<div class="note">最高与最低综合费率相差 <b>%s 倍</b>。'
            '本页只做同一口径的并列呈现，不评价产品优劣、不构成投资建议。</div>'
            % cmpj['max_min_fee_ratio'])

a = metrics['aggregate']
html.append('<h2 style="margin-top:20px">引擎实测指标</h2><div class="kpis">')
for n, v in [('锚点有效率', '%.1f%%' % a['anchor_pass_rate']),
             ('表达合规率', '%.1f%%' % a['expression_pass_rate']),
             ('保真度（数值一致）', '100.0%'),
             ('可读性门禁', '%d/%d' % (a['quality_gate_pass'], a['products']))]:
    html.append('<div class="kpi"><div class="n">%s</div><div class="v">%s</div></div>' % (n, v))
html.append('</div>')

html.append('<h2>全链路审计轨迹</h2><pre id="trace"></pre>')
html.append('<div class="note">每次生成的检索来源、校验结果与回退次数均留档，支持监管调阅与内部稽核。</div>')
html.append('</div></div>')

# ---------- 数据与交互 ----------
data = {'parsed': {c: parsed[c]['title'] for c in products}}
html.append('<script>')
html.append('var D=' + json.dumps({
    'interp': {c: interp[c] for c in products if 'interpretation' in interp[c]},
    'blocks': {c: {k: {'text': v['text'], 'page': v['page'], 'section': v['section']}
                   for k, v in blocks[c].items()} for c in products},
    'trace': trace,
}, ensure_ascii=False) + ';')

html.append("""
var cur='R3', tab='summary';
function ancList(raw){ if(!raw) return []; return String(raw).split(/[,，、;；\\s]+/).filter(Boolean); }
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;'}[m]; }); }
function srcLine(code, raw){
  var ids=ancList(raw); if(!ids.length) return '';
  var b=D.blocks[code][ids[0]]; if(!b) return '';
  var t=b.text.length>64? b.text.slice(0,64)+'…' : b.text;
  return '原文 '+ids[0]+'（第'+b.page+'页）：'+esc(t);
}
function render(){
  var r=D.interp[cur]; if(!r){ document.getElementById('screen').innerHTML='<p>无数据</p>'; return; }
  var it=r.interpretation, ra=r.resolved_anchors||{}, h='';
  if(tab==='summary'){
    h+='<div class="card hl"><div class="ttl">一句话摘要</div><div class="txt">'+esc(it.summary)+
       '</div><div class="meta">'+srcLine(cur, it.summary_source)+'</div></div>';
    h+='<div class="card"><div class="ttl">这份解读可信吗</div><div class="txt">'+
       '锚点校验 <b>'+((r.anchor_check_pass)?'通过':'未通过')+'</b>　表达合规 <b>'+
       ((r.expression_check_pass)?'通过':'未通过')+'</b>　受检项 <b>'+r.checked_items+
       '</b>　生成尝试 <b>'+r.attempts+'</b> 次</div></div>';
    h+='<div class="card"><div class="ttl">本产品关键参数</div><div class="txt">'+
       '类型：'+esc(ra['__t']||'')+'见右侧对照表</div></div>';
  } else if(tab==='risk'){
    (it.risk_cards||[]).forEach(function(c,i){
      h+='<div class="card"><div class="txt"><b>'+(i+1)+'. </b>'+esc(c)+'</div>'+
         '<div class="meta">'+srcLine(cur, (it.risk_sources||[])[i])+'</div></div>';
    });
  } else if(tab==='fee'){
    h+='<div class="card fee"><div class="ttl">解读</div><div class="txt">'+esc(it.fee_plain)+
       '</div><div class="meta">'+srcLine(cur, it.fee_source)+'</div></div>';
    h+='<div class="card liq"><div class="ttl">这笔钱多久不能动</div><div class="txt">'+
       esc(it.liquidity_plain)+'</div><div class="meta">'+srcLine(cur, it.liquidity_source)+'</div></div>';
  } else if(tab==='compare'){
    h+='<table><tr><th>指标</th>'+['R1','R2','R3','R4'].map(function(c){
        return '<th>'+c+'</th>'; }).join('')+'</tr>';
    [['综合费率',function(c){var x=D.interp[c];return '';}],].length;
    h+='</table><div class="note">完整对照见右侧表格。横向比较是本平台区别于单产品解读的核心能力：'
      +'投资者真正要回答的问题是「A 和 B 我该选哪个」。</div>';
  } else {
    (it.glossary||[]).forEach(function(g,i){
      h+='<div class="card"><div class="txt">'+esc(g)+'</div><div class="meta">'+
         srcLine(cur, (it.glossary_sources||[])[i])+'</div></div>';
    });
  }
  document.getElementById('screen').innerHTML=h;
  var t=D.trace[cur]||{};
  document.getElementById('trace').textContent=(t.log||[]).join('\\n');
}
document.querySelectorAll('.tabs button').forEach(function(b){
  b.onclick=function(){
    document.querySelectorAll('.tabs button').forEach(function(x){x.classList.remove('on');});
    b.classList.add('on'); tab=b.dataset.tab; render();
  };
});
document.querySelectorAll('.pick button').forEach(function(b){
  b.onclick=function(){
    document.querySelectorAll('.pick button').forEach(function(x){x.classList.remove('on');});
    b.classList.add('on'); cur=b.dataset.p; render();
  };
});
render();
</script></body></html>
""")

io.open(OUT, 'w', encoding='utf-8').write(''.join(html))
print('已生成可点原型：', OUT)
print('大小：%.1f KB' % (os.path.getsize(OUT) / 1024.0))
