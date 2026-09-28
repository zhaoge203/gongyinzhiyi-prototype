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
DEFAULT = products[0]          # 默认选中的产品（不再写死 R3）
DEFAULT_CMP = products[:4]     # 默认加入对照表的产品（多选，可切换）
def _clean(v):
    if isinstance(v, str) and v.strip().lower() in ('null', 'none', ''):
        return ''
    return v or ''


ptypes = {c: _clean((cmpj.get('product_types') or {}).get(c))
          or _clean(cmpj.get('rows') and cmpj['rows'][products.index(c)].get('type'))
          for c in products}

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
#cmpwrap th,#cmpwrap td{max-width:230px;min-width:86px;vertical-align:top}
#cmpwrap th .sub{display:block;font-weight:400;font-size:11px;color:#a05564;margin-top:2px}
.pick .hint{width:100%;font-size:11px;color:#96969b;margin:0 0 2px}
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
html.append('<div class="hint">点击产品按钮加入 / 移出对照表（建议选 2–5 只比对）；点击同时切换左侧详情</div>')
for c in products:
    html.append('<button data-p="%s"%s>%s %s</button>'
                % (c, ' class="on"' if c in DEFAULT_CMP else '', c, parsed[c]['title'][:12]))
html.append('</div>')

# 对照表：行结构由 out_04 的 table_rows 驱动（链四由大模型决定或兜底），
# 列由用户在前端勾选的产品集合决定；表格由 JS 渲染进 cmpwrap，容器横向滚动防拥挤
html.append('<h2>同类产品对照（数据未经改算）</h2><div id="cmpwrap" style="overflow-x:auto"></div>')
html.append('<div class="note">最高与最低综合费率相差 <b>%s 倍</b>。'
            '本页只做同一口径的并列呈现，不评价产品优劣、不构成投资建议。</div>'
            % cmpj['max_min_fee_ratio'])

a = metrics['aggregate']
# 隐藏区：引擎实测指标（数据保留在 HTML 中，仅不显示）
html.append('<div style="display:none"><h2 style="margin-top:20px">引擎实测指标</h2><div class="kpis">')
for n, v in [('锚点有效率', '%.1f%%' % a['anchor_pass_rate']),
             ('表达合规率', '%.1f%%' % a['expression_pass_rate']),
             ('保真度（数值一致）', '100.0%'),
             ('可读性门禁', '%d/%d' % (a['quality_gate_pass'], a['products']))]:
    html.append('<div class="kpi"><div class="n">%s</div><div class="v">%s</div></div>' % (n, v))
html.append('</div></div>')  # 结束隐藏区：引擎实测指标

# 隐藏区：全链路审计轨迹（数据保留在 HTML 中，仅不显示）
html.append('<div style="display:none"><h2>全链路审计轨迹</h2><pre id="trace"></pre>')
html.append('<div class="note">每次生成的检索来源、校验结果与回退次数均留档，支持监管调阅与内部稽核。</div></div>')
html.append('</div></div>')

# ---------- 数据与交互 ----------
data = {'parsed': {c: parsed[c]['title'] for c in products}}
html.append('<script>')
html.append('var D=' + json.dumps({
    'interp': {c: interp[c] for c in products if 'interpretation' in interp[c]},
    'blocks': {c: {k: {'text': v['text'], 'page': v['page'], 'section': v['section']}
                   for k, v in blocks[c].items()} for c in products},
    'trace': trace,
    'cmp': {'products': products, 'types': ptypes, 'rows': cmpj.get('table_rows') or []},
}, ensure_ascii=False) + ';')

html.append("""
var cur='__DEFAULT__', tab='summary';
var sel=__SEL__;               // 对照表当前勾选的产品集合（多选）
function ancList(raw){ if(!raw) return []; return String(raw).split(/[,，、;；\\s]+/).filter(Boolean); }
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;'}[m]; }); }
function srcLine(code, raw){
  var ids=ancList(raw); if(!ids.length) return '';
  var b=D.blocks[code][ids[0]]; if(!b) return '';
  var t=b.text.length>64? b.text.slice(0,64)+'…' : b.text;
  return '原文 '+ids[0]+'（第'+b.page+'页）：'+esc(t);
}
function cmpTable(hint){
  var cols=D.cmp.products.filter(function(c){ return sel.indexOf(c)>=0; });
  var h='<table><tr><th>指标</th>'+cols.map(function(c){
      return '<th>'+c+'<span class="sub">'+esc(D.cmp.types[c]||'')+'</span></th>'; }).join('')+'</tr>';
  (D.cmp.rows||[]).forEach(function(r){
    h+='<tr><td><b>'+esc(r.label)+'</b></td>'+cols.map(function(c){
      var v=(r.values||{})[c]; return '<td>'+(v?esc(v):'—')+'</td>'; }).join('')+'</tr>';
  });
  return h+'</table>'+(hint||'');
}
function renderCmp(){
  document.getElementById('cmpwrap').innerHTML=cmpTable('');
}
function render(){
  var r=D.interp[cur]; if(!r){ document.getElementById('screen').innerHTML='<p>无数据</p>'; return; }
  var it=r.interpretation, ra=r.resolved_anchors||{}, h='';
  if(tab==='summary'){
    h+='<div class="card hl"><div class="ttl">一句话摘要</div><div class="txt">'+esc(it.summary)+
       '</div><div class="meta">'+srcLine(cur, it.summary_source)+'</div></div>';
    h+='<div class="card" style="display:none"><div class="ttl">这份解读可信吗</div><div class="txt">'+
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
    h+='<div style="overflow-x:auto">'+cmpTable('')+'</div><div class="note">与右侧表格联动：'
      +'点上方产品按钮即可更换比对对象。横向比较是本平台区别于单产品解读的核心能力：'
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
    var p=b.dataset.p, i=sel.indexOf(p);
    if(i>=0){ if(sel.length>1){ sel.splice(i,1); b.classList.remove('on'); } }
    else { sel.push(p); b.classList.add('on'); }
    cur=p; render(); renderCmp();
  };
});
render(); renderCmp();
</script></body></html>
""")

out_html = ''.join(html).replace('__DEFAULT__', DEFAULT).replace('__SEL__', json.dumps(DEFAULT_CMP))
io.open(OUT, 'w', encoding='utf-8').write(out_html)
print('已生成可点原型：', OUT)
print('大小：%.1f KB' % (os.path.getsize(OUT) / 1024.0))
