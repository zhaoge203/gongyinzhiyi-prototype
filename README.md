# 工银智译 · 原型系统

参赛策划案《工银智译——金融产品资料概要智能解读平台》的配套可运行原型。
原型的全部指标与结论均可由本仓库代码复现。

## 目录结构

```
├── 工银智译_原型/          可运行原型（引擎 + 交互界面）
│   ├── data/                 输入：4 份真实产品资料概要（官方 PDF）
│   ├── engine/               引擎源码
│   │   ├── chain1_parse.py     链一 文档解析与语义分块
│   │   ├── chain2_extract.py   链二 要素结构化抽取 + 正则交叉校验
│   │   ├── chain3_interpret.py 链三 分层解读生成 + 认知确认题 + 锚点/表达校验
│   │   ├── chain4_compare.py   链四 同类产品对照 + 链五 质量评测
│   │   ├── chain6_graph.py     链六 LangGraph 状态机（含真实 human-in-the-loop）
│   │   ├── fidelity.py         保真度与可读性度量的唯一定义（共享）
│   │   ├── probe_fidelity2.py  保真度指标检出能力探针
│   │   ├── run_all.py          一键跑通全部链条
│   │   └── out_0*.json         8 份结构化产出物
│   ├── ui/
│   │   ├── prototype.html      可点交互原型（单文件，浏览器直接打开）
│   │   ├── render_ui.py        界面稿渲染脚本（PIL）
│   │   └── ui_*.png            4 张界面稿
│   ├── README.md               原型详细说明（运行方式 / 产出物对照表）
│   └── 审计报告.md
│
└── 工银智译_生成源文件/    策划案文档的生成源文件
    ├── content.py              文档内容源
    ├── build_docx.py           由内容源构建 docx
    ├── build_txt.py / verify.py
    ├── structure.txt           文档结构
    ├── examples.txt / extract_examples.py / extract_result.txt
    └── ref_images.txt          配图清单
```

## 快速开始

详见 [工银智译_原型/README.md](工银智译_原型/README.md)。

```bash
# 依赖：langchain-core, langchain-deepseek, langgraph, pypdf, pydantic
# 大模型：DeepSeek（环境变量 DEEPSEEK_API_KEY）

cd 工银智译_原型/engine
python run_all.py               # 一键跑通全部链条（约 3–6 分钟）
```

> 环境说明：`engine/*.py` 使用 **Python 3.12**（langchain / langgraph）；
> `ui/render_ui.py`、`ui/build_prototype.py` 需 **Python 3.9**（依赖随附的 Pillow）。
> 可点原型 `prototype.html` 为单文件、无外部依赖，双击即可打开。
