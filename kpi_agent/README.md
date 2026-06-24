# Project KPI Intelligence Agent

竞技体育 KPI 智能体 — 基于表现目标 (PO) 驱动的项目 KPI 建模与数据库系统。

## 核心流程

```
PO → 项目需求分析 → 表现决定因素模型 → KPI → 评估 → 干预 → 检查迭代
```

## 技术栈

- **Backend**: FastAPI + SQLAlchemy + Pydantic v2
- **Database**: SQLite (MVP) / PostgreSQL (production)
- **Vector DB**: Chroma (Phase 2)
- **Frontend**: Streamlit (Phase 2)

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库并加载示例数据

```bash
python -m app.seed
```

### 3. 启动 API 服务

```bash
uvicorn app.main:app --reload
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 实体 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/projects` | 创建项目 |
| GET | `/projects` | 列出所有项目 |
| GET | `/projects/{id}` | 获取项目详情 |
| PUT | `/projects/{id}` | 更新项目 |
| DELETE | `/projects/{id}` | 删除项目 |
| POST | `/outcomes/projects/{id}` | 创建 PO |
| GET | `/outcomes/projects/{id}` | 列出项目 PO |
| POST | `/determinants/projects/{id}` | 创建决定因素 |
| GET | `/determinants/projects/{id}/tree` | 获取决定因素树 |
| POST | `/kpis/projects/{id}` | 创建 KPI |
| GET | `/kpis/projects/{id}` | 列出项目 KPI |
| POST | `/kpis/{id}/measurements` | 添加 KPI 测量 |
| GET | `/kpis/{id}/trend` | KPI 趋势分析 |
| GET | `/athletes/{id}/dashboard` | 运动员仪表盘 |
| POST | `/reports/projects/{id}/generate` | 生成报告 |

### Agent 工作流

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/create-project` | 工作流1: 创建项目 |
| POST | `/agent/define-po` | 工作流2: 定义 PO |
| POST | `/agent/analyze-demands` | 工作流3: 项目需求分析 |
| POST | `/agent/build-performance-model` | 工作流4: 建立表现模型 |
| POST | `/agent/generate-kpis` | 工作流5: 生成 KPI |
| POST | `/agent/evaluate-athlete` | 工作流6: 评估运动员 |
| POST | `/agent/generate-intervention-plan` | 工作流7: 干预计划 |
| POST | `/agent/generate-report` | 工作流8: 生成报告 |

## 内置示例：800 米精英项目

运行 `python -m app.seed` 会创建：

- **1 个项目**: Elite 800m Performance Project
- **3 个 PO**: 成绩目标 1:48.00、决赛资格、缩小差距
- **2 名运动员**: 国家级 800m 专项运动员
- **20+ 个表现决定因素**: 生理、健康、技术、战术、心理、规则
- **20+ 个 KPI**: VO2max、乳酸阈、最大速度、RSI、不对称性等
- **10 项干预措施**: 长跑、节奏跑、HIIT、力量训练、技术训练等
- **60+ 条测量记录**: 模拟3个时间点的测试数据
- **4 条证据来源**: 文献、官方规则、教练经验
- **1 份示例报告**: PO与KPI设计报告

## 项目结构

```
kpi_agent/
  app/
    __init__.py
    main.py              # FastAPI entrypoint
    database.py          # SQLAlchemy engine & session
    models.py            # ORM models (15 tables)
    schemas.py           # Pydantic schemas
    crud.py              # CRUD operations
    seed.py              # 800m seed data
    agent/
      __init__.py
      workflows.py       # 8 agent workflows
      performance_model.py  # Determinant builder
      kpi_generator.py   # KPI generator
      report_generator.py  # Markdown report generator
    routers/
      __init__.py
      projects.py        # Project CRUD
      outcomes.py        # PO CRUD
      determinants.py    # Determinant CRUD + tree
      kpis.py            # KPI CRUD + measurements + trend
      athletes.py        # Athlete CRUD + dashboard
      evidence.py        # Evidence sources + upload
      reports.py         # Report generation + listing
      agent.py           # Agent workflow endpoints
      literature.py      # Literature search + extraction
      performance_model.py  # Lit-to-model pipeline (NEW)
    literature/          # Free literature search module
      ...
      connectors/        # 6 free data source connectors
    performance_model/   # Literature → Performance Model (NEW)
      taxonomy.py        # 8 categories + 2000+ keywords
      batch_loader.py    # Batch literature reader
      extractor.py       # Multi-method determinant extractor
      merger.py          # Candidate dedup + merge
      builder.py         # Performance model hierarchy builder
      evidence_linker.py # Evidence linking + report
      pipeline.py        # End-to-end orchestration
  tests/
    test_basic.py        # Smoke tests
    test_literature_quick.py
    test_performance_model_pipeline.py  # (NEW)
  README.md
  requirements.txt
```

## 运行测试

```bash
cd kpi_agent
python -m pytest tests/test_basic.py -v
```

## 数据库模型 (15 表)

- `projects` — 项目
- `performance_outcomes` — 表现目标 PO
- `athletes` — 运动员
- `performance_determinants` — 表现决定因素（支持分层）
- `kpis` — 关键表现指标
- `kpi_measurements` — KPI 测量记录
- `interventions` — 干预措施
- `assessments` — 评估记录
- `competitions` — 比赛
- `competition_results` — 比赛结果
- `evidence_sources` — 证据来源
- `documents` — 上传文档
- `rules` — 比赛规则
- `reports` — 报告
- `audit_logs` — 审计日志

## 核心设计原则

1. **PO 驱动**: KPI 不能凭空产生，必须先明确表现目标
2. **证据分级**: 每条信息标注证据等级（高/中/低/专家经验/未知）
3. **分层模型**: 支持 PO → 决定因素 → 子因素 → 干预 → KPI 的层次结构
4. **动态迭代**: 模型随新知识、新数据、新规则变化而更新
5. **多项目类型**: 支持计量类、非计量类、团队类项目

## Literature to Performance Model（文献 → 表现模型）

### 功能目标

从已检索的文献中批量提取表现决定因素，自动归类到8大表现决定因素层级，构建带证据链接的层级模型。

### 工作流程

```
已检索文献 → 批量读取 title/abstract → 多方法提取指标 →
自动归入8大类别 → 去重合并 → 评分 → 构建层级模型 →
人工确认/拒绝 → 保存到项目数据库
```

### 8大决定因素分类体系

| 类别 | Key | 说明 |
|------|-----|------|
| 生理要求 | `physiological_requirements` | VO2max、乳酸阈、跑步经济性、力量、速度、功率等 |
| 技术要求 | `technical_requirements` | 技术、运动模式、步幅、步频、触地时间、生物力学等 |
| 战术要求 | `tactical_requirements` | 配速策略、决策、比赛策略、定位、团队配合等 |
| 营养要求 | `nutritional_requirements` | 碳水摄入、补液、咖啡因、肌酸、体成分等 |
| 心理技能 | `psychological_skills` | 反应时、焦虑、注意力、自信心、心理韧性等 |
| 器材特点 | `equipment_characteristics` | 鞋类、可穿戴设备、自行车、球拍、运动表面等 |
| 健康 | `health` | 损伤风险、恢复、睡眠、训练负荷、过度训练等 |
| 比赛规则 | `competition_rules` | 评分系统、资格标准、比赛形式、排名系统等 |

### 使用的免费开源包

**核心（第一优先级）:**
- `sentence-transformers` (all-MiniLM-L6-v2) — 可选，语义匹配增强
- `keybert` — 可选，语义关键词提取
- `yake` — 轻量级无监督关键词提取
- `rapidfuzz` — 指标名称去重和模糊匹配合并
- `spacy` (en_core_web_sm) — 可选，名词短语提取

**所有方案均为免费本地运行，不调用商业 LLM API。**

### 提取方法（多方法融合，自动 fallback）

1. **领域词典匹配**（始终可用）— 2000+ 关键词覆盖8大类别
2. **正则模式匹配**（始终可用）— 20种常见指标模式
3. **YAKE**（需安装 `yake`）— 无监督关键词，自动 fallback
4. **KeyBERT**（需安装 `keybert`）— 语义关键词，自动 fallback
5. **spaCy**（需安装 `spacy`）— 名词短语，自动 fallback

### 运行示例

```bash
# 1. 先检索文献（通过 Streamlit UI 或 API）
# 2. 进入「文献→表现模型」页面
# 3. 选择已缓存的检索查询
# 4. 点击「从文献批量提取表现决定因素」
# 5. 展开查看证据详情，接受/拒绝候选
# 6. 点击「保存到当前项目」

# 或通过 API:
curl -X POST http://localhost:9999/performance-model/extract-from-literature \
  -H "Content-Type: application/json" \
  -d '{"query_id": 1, "limit": 50, "min_confidence": 0.2}'

curl -X GET http://localhost:9999/performance-model/tree?query_id=1

curl -X GET "http://localhost:9999/performance-model/export?query_id=1&format=markdown"
```

### 如何查看证据链接的表现模型

- 在 Streamlit UI 页面「🧬 文献→表现模型」中：
  - 查看「候选指标列表」表格
  - 展开每个候选查看「证据详情」
  - 在「层级结构展示」中查看8大类分布
  - 导出 JSON / CSV / Markdown

### 人工确认候选

- 每个候选指标可标记为 `candidate`（待定）、`accepted`（接受）、`rejected`（拒绝）
- 只有标记为 `accepted` 的候选才能保存到项目数据库
- 保存后自动创建 `PerformanceDeterminant` 层级记录

### 免费方案限制

1. 不调用 OpenAI / Anthropic / 付费 LLM
2. 不使用付费数据库（PubMed、Scopus 等）
3. 不绕过 paywall 获取全文
4. 所有指标抽取必须可追溯到原文句子
5. 不确定的内容标记为 `other_uncertain`
6. 不会将模糊概念自动变成高置信决定因素
7. 单篇文献不会生成高于 "低" 置信度的候选

### Fallback 机制

- KeyBERT 不可用 → YAKE
- YAKE 不可用 → 领域词典 + 正则（始终可用）
- sentence-transformers 不可用 → rapidfuzz 字符串模糊匹配
- spaCy 不可用 → 跳过 NP 提取
- 某篇文献缺少摘要 → 仅用标题，记录 warning
- 某篇文献无任何内容 → 跳过，记录 warning

### 新增 API 端点

| Method | Path | Description |
|--------|------|-------------|
| POST | `/performance-model/extract-from-literature` | 完整提取管线 |
| GET | `/performance-model/candidates` | 获取候选列表 |
| GET | `/performance-model/tree` | 获取层级模型树 |
| GET | `/performance-model/queries` | 获取已缓存检索查询 |
| GET | `/performance-model/export` | 导出（JSON/CSV/Markdown） |
| GET | `/performance-model/documents` | 获取缓存文献列表 |
| POST | `/performance-model/save-to-project` | 保存到项目数据库 |

### 新增项目文件

```
app/
  performance_model/
    __init__.py
    taxonomy.py          # 8大类别 + 2000+ 关键词 + 标准化映射
    batch_loader.py      # 从文献缓存读取批量文献
    extractor.py         # 多方法提取器（词典/YAKE/KeyBERT/spaCy）
    merger.py            # 候选去重合并
    builder.py           # 表现模型层级构建器
    evidence_linker.py   # 证据链接 + Markdown 报告
    pipeline.py          # 端到端流水线编排
  routers/
    performance_model.py # FastAPI 端点
tests/
  test_performance_model_pipeline.py
```
