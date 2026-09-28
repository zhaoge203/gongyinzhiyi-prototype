# 工银智译 · 原型系统

参赛策划案《工银智译——金融产品资料概要智能解读平台》的配套可运行原型。
全部指标与结论均可由本仓库代码复现。

## 特性

- **六链引擎**：PDF 解析分块 → 要素抽取（LLM + 正则交叉校验）→ 分层解读生成（含认知确认题）→ 同类对照 + 质量评测 → LangGraph 状态机（含真实 human-in-the-loop 人工复核闸门）→ 保真度探针
- **保真可溯**：每条解读带锚点，可跳回原文出处；对照数据「未经改算」
- **异构文档自适应**：产品资料概要 / 招募说明书 / 基金合同 / 季报 / 银行理财说明书均可解析；对照表的行由大模型按各产品实际披露的指标决定，失败自动退回固定行兜底
- **文件名零要求**：产品编号自动分配（P01…），按内容 MD5 去重；引擎不依赖任何文件名约定
- **交互原型**：产品多选比对、流动性时间轴、风险卡分类着色、全横杠行自动隐藏；指标卡/审计轨迹数据保留在 HTML 中但默认隐藏

## 目录结构

```
工银智译_原型/
├── run.py                 一键入口（引擎全链路 + 生成 HTML）
├── requirements.txt       依赖清单
├── .env.example           API Key 模板（复制为 engine/.env 使用）
├── README.md / 审计报告.md
├── data/                  输入：产品资料 PDF（支持子文件夹，文件名随意）
├── data resource/         备用文件区（引擎不扫描，仅存放）
├── engine/                引擎源码
│   ├── chain1_parse.py      链一 文档解析与语义分块（自动编号 + 内容去重）
│   ├── chain2_extract.py    链二 要素结构化抽取 + 正则交叉校验（含额外指标）
│   ├── chain3_interpret.py  链三 分层解读生成 + 认知确认题 + 锚点/表达校验
│   ├── chain4_compare.py    链四 同类对照（LLM 决定表格行，兜底固定行）+ 链五 质量评测
│   ├── chain6_graph.py      链六 LangGraph 状态机（人工复核 interrupt 演示；支持分块执行）
│   ├── fidelity.py          保真度与可读性度量的唯一定义（共享）
│   ├── probe_fidelity2.py   保真度指标检出能力探针
│   ├── run_all.py           一键跑通全部链条
│   ├── .env                 DeepSeek API Key（不入库）
│   └── out_0*.json          结构化产出物（可重新生成）
└── ui/
    ├── build_prototype.py   由引擎产出生成单文件可点原型
    ├── prototype.html       可点原型（浏览器直接打开）
    └── ui_*.png             界面稿
```

## 快速开始

```bash
# 1. 安装依赖（Python 3.10+，开发验证于 3.12 / 3.14）
pip install -r requirements.txt

# 2. 配置 DeepSeek API Key
cp .env.example engine/.env      # Windows: copy .env.example engine\.env
#   然后编辑 engine/.env，把 key 换成你自己的

# 3. 放入产品资料 PDF 到 data/（随意命名、可分子文件夹）

# 4. 一键运行
python run.py
```

完成后浏览器打开 `ui/prototype.html` 即可演示。

## 分步执行（可选）

```bash
cd engine
python run_all.py             # 或单链：python chain1_parse.py 等
python chain6_graph.py demo   # 只跑人工复核演示
cd ../ui
python build_prototype.py     # 重新生成 HTML
```

## 增减产品

把 PDF 放进/移出 `data/` 后重跑 `python run.py` 即可。无需关心文件名；
同一产品放了两份时会按内容 MD5 自动去重并提示。

## 环境说明

- 大模型：DeepSeek（`deepseek-chat`），通过环境变量 `DEEPSEEK_API_KEY` 或 `engine/.env` 配置
- 全文引擎仅需 `requirements.txt` 五个包，均为纯 pip 安装，无系统依赖
- 成本：每只产品约 2–3 次 LLM 调用；对照表行规划全表仅 1 次调用

## 已知限制（如实记录）

- 非标准概要格式（招募书/合同/理财说明书）没有「六大章节」结构，锚点小节归属与可读性
  基线会降级，相关指标（门禁/保真度）不再全 100%，引擎会保守处理并在轨迹中留痕
- `probe_fidelity2.py` 的 A 部分（对抗样本）预期与实现存在历史偏差：同小节内的
  数值对调超出当前校验窗口的检测能力，B 部分（真实产出评测）不受影响
