# Sports Science Research Agent

运动科学文献智能体 — 面向运动科学学术研究的独立 Agent 系统。

## 功能概览

| 模块 | 功能 |
|------|------|
| 📥 文献导入 | DOI / PMID 查询、PDF 上传解析、手动录入、BibTeX/RIS 导入 |
| 🔍 文献库检索 | 关键词搜索、按研究类型/证据等级/领域/年份筛选 |
| 🧪 文献筛选 | 自动判断纳入/排除，质量评分 (0-10)，偏倚风险评估 |
| ❓ 学术问答 | 基于文献库的 RAG 检索增强生成，按证据等级回答 |
| ✍️ 论文写作 | 生成 Introduction/Methods/Discussion/综述/假设等 |
| 📈 证据地图 | 领域 × 研究类型 × 质量的可视化证据分布 |

## 快速启动

### 1. 创建虚拟环境

```bash
cd sports_science_agent
python -m venv .venv
```

### 2. 激活虚拟环境

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量（可选）

```bash
cp .env.example .env
# 编辑 .env 填入 API key（不填也可运行，本地功能完整）
```

### 5. 启动应用

```bash
streamlit run app.py --server.port 8502
```

浏览器访问: **http://localhost:8502**

## 项目结构

```
sports_science_agent/
├── app.py                  # Streamlit 主应用
├── requirements.txt        # 依赖清单
├── .env.example            # 环境变量模板
├── README.md
├── src/
│   ├── config.py           # 集中配置
│   ├── database.py         # 文献库 CRUD（JSON/CSV）
│   ├── literature_importer.py  # 文献导入统一接口
│   ├── pdf_parser.py       # PDF 文本提取
│   ├── metadata_extractor.py   # DOI/PMID 元数据查询
│   ├── screening.py        # 文献筛选决策
│   ├── quality_assessment.py   # 质量评分与偏倚评估
│   ├── vector_store.py     # ChromaDB 向量存储
│   ├── rag_engine.py       # RAG 检索增强生成
│   ├── evidence_synthesizer.py # 证据综合
│   ├── academic_writer.py  # 学术写作生成
│   ├── citation_manager.py # 引用格式管理
│   └── utils.py            # 工具函数
├── data/                   # PDF 原文与解析文本
├── literature_db/          # 文献元数据（JSON/CSV）
├── vector_store/           # ChromaDB 向量索引
├── papers/                 # 导入的 PDF 副本
├── outputs/                # 输出文件
├── logs/                   # 日志
└── prompts/                # 提示词模板（预留）
```

## 端口隔离

- 旧项目运行在 `http://localhost:8501`
- 本项目运行在 `http://localhost:8502`
- 两个项目互不影响，各自独立

## 文献筛选标准

### 优先纳入
- 系统综述、Meta 分析、RCT、前瞻性队列研究
- 高质量横断面研究、实验研究、运动干预研究
- 国际权威指南或专家共识
- 顶级或高影响力期刊文章

### 评分体系
- **quality_score**: 0-10（研究设计 + 样本量 + 方法学 + 报告 + 来源）
- **relevance_score**: 0-10（与运动科学领域的关键词匹配度）
- **evidence_level**: high / moderate / low / very_low
- **risk_of_bias**: low / some_concerns / high / unclear

### 纳入阈值
- quality_score ≥ 6 且 relevance_score ≥ 6 → include
- 高优先级: quality ≥ 8, relevance ≥ 8, 且为 meta/RCT/指南

## 学术回答原则

Agent 在回答学术问题时遵循：
1. 优先基于本地文献库，不编造文献
2. 明确区分证据等级（high/moderate/low/very_low）
3. 使用学术语言（"现有证据提示……""部分研究存在……"）
4. 主动指出研究局限和研究空白
5. 证据不足时明确说明

## 引用格式

支持 APA / Vancouver / AMA / GB/T 7714 四种格式。

## 后续扩展建议

1. 接入 PubMed / CrossRef / Semantic Scholar 完整检索
2. 自动检索 + 自动筛选 + 自动入库的流水线
3. 多语言支持优化（中文文献检索）
4. 知识图谱可视化
5. 协作筛选模式（多用户）
6. PDF 全文段落级解析（IMRaD 结构化提取）
7. 自动 Meta 分析数据提取表
8. PRISMA 流程图自动生成
