# -*- coding: utf-8 -*-
"""
工银智译 · 原型引擎 — 链二：风险与费用要素结构化抽取
用 LangChain + DeepSeek 结构化输出抽取标准风险条目，
再与确定性正则抽取结果交叉校验（保真度校验的第一道防线）。

设计原则：LLM 负责「从非结构化文本里找字段」，正则负责「算得出来的数」，
两者不一致即判定为低置信，进入人工复核队列 —— 这正是策划案里承诺的机制。
"""
import io
import json
import os
import re
import sys
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '工银智译_生成源文件'))


class RiskItem(BaseModel):
    category: str = Field(description="风险类别，从：流动性风险/市场风险/信用风险/杠杆风险/汇率与跨境风险/操作与合规风险/机制特有风险 中选择")
    name: str = Field(description="风险名称，简短，如「侧袋机制」「最短持有期」")
    plain: str = Field(description="用普通投资者能懂的一句话说明这个风险意味着什么")
    source_quote: str = Field(description="支撑上述结论的原文片段，必须逐字摘自输入文本")


class Indicator(BaseModel):
    name: str = Field(description="指标名称，简短规范，如「起购金额」「业绩比较基准」「产品期限」")
    value: str = Field(description="指标取值，直接摘自原文，如「1元」「沪深300指数」")
    source_quote: str = Field(description="支撑该指标的原文片段，必须逐字摘自输入文本")


class Facts(BaseModel):
    product_type: Optional[str] = Field(None, description="基金类型/产品类型")
    operation: Optional[str] = Field(None, description="运作方式")
    open_frequency: Optional[str] = Field(None, description="开放频率")
    min_holding: Optional[str] = Field(None, description="最短持有期，没有则填「无」")
    redemption_rule: Optional[str] = Field(None, description="申购赎回费用规则的一句话概括")
    comprehensive_fee: Optional[str] = Field(None, description="基金运作综合费率（年化）")
    management_fee: Optional[str] = Field(None, description="管理费率")
    custodian_fee: Optional[str] = Field(None, description="托管费率")
    sales_service_fee: Optional[str] = Field(None, description="销售服务费率，没有则填「无」")
    benchmark: Optional[str] = Field(None, description="业绩比较基准")
    risk_items: List[RiskItem] = Field(default_factory=list, description="识别出的风险条目，按重要性降序")
    extra_indicators: List[Indicator] = Field(
        default_factory=list,
        description="文档中明确披露的、适合跨产品对照的其他客观指标"
                    "（如起购金额、业绩比较基准、产品期限、收益分配方式、风险等级等），宁缺勿错")


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是银行财富管理条线的合规资料整理员。你的唯一任务是从「基金产品资料概要」原文片段中"
     "抽取客观字段，并把专业表述转写成普通投资者能听懂的一句话。\n"
     "硬性约束：\n"
     "1) 只使用输入文本中明确出现的信息，不得推断、不得补充外部知识、不得改变任何数值；\n"
     "2) source_quote 必须逐字摘自输入文本，不得改写；\n"
     "3) 找不到的字段填 null，无法确认的信息宁缺勿错；\n"
     "4) 不给出投资建议，不使用「稳健」「安全」「推荐」等评价性词汇；\n"
     "5) 文档中明确披露的其他可对照客观指标（如起购金额、业绩比较基准、产品期限、"
     "收益分配方式、风险等级、投资范围等）一并收录进 extra_indicators，宁缺勿错。"),
    ("human", "产品代码：{code}\n\n以下是该产品的产品资料概要原文片段：\n\n{context}"),
])

# 相关性筛选：只喂与费用/流动性/风险相关的块，控制上下文长度
KEY_HINT = ['费率', '费用', '管理费', '托管费', '销售服务费', '赎回', '申购', '持有期',
            '风险', '基准', '投资范围', '运作方式', '开放频率', '基金类型', '侧袋',
            '期货', '港股通', '存托凭证', '资产支持证券', '杠杆', '清算', '终止']


def pick_context(blocks, limit=9000):
    """KFS 的 PDF 表格经文本抽取后常被压平：标签与数值分散在相邻两行，
    例如 B075=「基金运作综合费率（年化）」、B076=「0.45%」。
    直接按行喂给模型会让数值变成孤立数字而丢失锚点，因此这里对相邻块做
    标签-数值邻近合并，把「标签 → 值」显式拼回同一行。"""
    picked, seen = [], set()
    for i, b in enumerate(blocks):
        t = b['text']
        if len(t) < 2 or t in seen:
            continue
        relevant = any(k in t for k in KEY_HINT) or b['section'] in (
            '投资本基金涉及的费用', '风险揭示与重要提示')
        if not relevant:
            continue
        seen.add(t)
        label = '%s|第%d页' % (b['id'], b['page'])
        # 若下一块是纯数值（表格被压平的值行），合并进来
        if i + 1 < len(blocks):
            nxt = blocks[i + 1]['text'].strip()
            if re.fullmatch(r'[\d,\.]+%?|[\d,]+\.\d{2}\s*元', nxt) and len(nxt) <= 20:
                picked.append('[%s] %s → %s' % (label, t, nxt))
                seen.add(nxt)
                continue
        picked.append('[%s] %s' % (label, t))
    return '\n'.join(picked)[:limit]


# ---------- 确定性抽取（交叉校验基准） ----------
def regex_facts(doc):
    text = '\n'.join(b['text'] for b in doc['blocks'])
    out = {}
    m = re.search(r'基金运作综合费率（年化）\s*([\d.]+%)', text)
    out['comprehensive_fee'] = m.group(1) if m else None
    i = text.find('基金运作相关费用')
    seg = text[i:i + 1200] if i > 0 else text
    for k, fn in [('management_fee', '管理费'), ('custodian_fee', '托管费'),
                  ('sales_service_fee', '销售服务费')]:
        m = re.search(re.escape(fn) + r'\s*([\d.]+%)', seg)
        out[k] = m.group(1) if m else None
    m = re.search(r'([一二三四五六七八九十\d]+)\s*年最短持有期', text)
    out['min_holding'] = (m.group(1) + '年') if m else '无'
    out['no_redemption_fee'] = bool(re.search(r'本基金不收取赎回费', text))
    out['no_purchase_fee'] = bool(re.search(r'不收取申购费用和赎回费用', text))
    out['side_pocket'] = '侧袋机制' in text
    out['has_leverage'] = bool(re.search(r'杠杆|保证金交易|强制平仓', text))
    out['hk_connect'] = '港股通' in text
    return out


def cross_check(llm_f, rg):
    """比对 LLM 抽取与正则抽取，返回 (是否通过, 差异列表)"""
    diffs = []
    for key in ['comprehensive_fee', 'management_fee', 'custodian_fee', 'sales_service_fee']:
        a = (llm_f.get(key) or '').replace(' ', '')
        b = (rg.get(key) or '').replace(' ', '')
        if b and a and a != b:
            diffs.append('%s: LLM=%s 正则=%s' % (key, a, b))
        if b and not a:
            diffs.append('%s: LLM未抽取 正则=%s' % (key, b))
    a = (llm_f.get('min_holding') or '')
    b = rg.get('min_holding') or ''
    if b and b != '无' and b not in a:
        diffs.append('min_holding: LLM=%s 正则=%s' % (a, b))
    return (len(diffs) == 0), diffs


def _load_deepseek_key():
    """优先环境变量 DEEPSEEK_API_KEY；否则依次找 engine/.env、项目根 .env。"""
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key:
        return key.strip().strip('"').strip("'")
    for path in (os.path.join(HERE, '.env'),
                 os.path.join(os.path.dirname(HERE), '.env'),
                 r'D:\MyStudy\FTEC5660\.env'):
        if os.path.exists(path):
            for ln in io.open(path, encoding='utf-8'):
                m = re.match(r'^DEEPSEEK_API_KEY\s*=\s*(.+)$', ln.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    return None


def _norm(v):
    """把 LLM 输出的字符串 'null'/'none'/空串 归一化为 None（治本：
    部分文档没有某字段时，模型会填字符串 "null" 而非 JSON null）。"""
    if isinstance(v, str) and v.strip().lower() in ('null', 'none', 'n/a', ''):
        return None
    return v


def _norm_facts(fd):
    for k, v in list(fd.items()):
        if isinstance(v, str):
            fd[k] = _norm(v)
    return fd


def main():
    key = _load_deepseek_key()
    if not key:
        raise SystemExit('未找到 DEEPSEEK_API_KEY（请设置环境变量，或在 engine/.env 中写入 DEEPSEEK_API_KEY=...）')
    os.environ['DEEPSEEK_API_KEY'] = key

    parsed = json.load(io.open(os.path.join(HERE, 'out_01_parsed.json'), encoding='utf-8'))
    llm = ChatDeepSeek(model='deepseek-chat', temperature=0, max_tokens=4000)
    structured = llm.with_structured_output(Facts)
    chain = PROMPT | structured

    results = {}
    for code in sorted(parsed):
        doc = parsed[code]
        ctx = pick_context(doc['blocks'])
        print('--- %s 上下文 %d 字 ---' % (code, len(ctx)))
        try:
            facts = chain.invoke({'code': code, 'context': ctx})
            fd = _norm_facts(facts.model_dump())
        except Exception as e:
            print('   LLM 抽取失败：%s' % str(e)[:160])
            results[code] = {'error': str(e)[:200], 'regex': regex_facts(doc)}
            continue
        rg = regex_facts(doc)
        ok, diffs = cross_check(fd, rg)
        results[code] = {
            'llm': fd,
            'regex': rg,
            'cross_check_pass': ok,
            'diffs': diffs,
            'context_chars': len(ctx),
        }
        print('   类型=%s | 综合费率=%s | 最短持有期=%s | 风险条目=%d | 交叉校验=%s'
              % (fd.get('product_type'), fd.get('comprehensive_fee'),
                 fd.get('min_holding'), len(fd.get('risk_items') or []),
                 '通过' if ok else ('不通过 ' + '; '.join(diffs))))

    with io.open(os.path.join(HERE, 'out_02_facts.json'), 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print('\n已写出 out_02_facts.json')


if __name__ == '__main__':
    main()
