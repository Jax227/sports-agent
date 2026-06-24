"""
FastAPI application entrypoint for the KPI Agent.

Run:
    uvicorn app.main:app --reload

The application provides:
- Full CRUD for all entities (projects, POs, determinants, KPIs, etc.)
- 8 Agent workflow endpoints for the KPI lifecycle
- Report generation (Markdown)
- Database auto-creation on startup
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import (
    projects, outcomes, determinants, kpis,
    athletes, evidence, reports, agent, literature, performance_model,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Project KPI Intelligence Agent",
    description="""
## 竞技体育 KPI 智能体

核心工作流: **PO → 项目需求分析 → 表现决定因素 → KPI → 评估 → 干预 → 迭代**

### 关键原则
- KPI 必须关联 PO 和表现决定因素
- 必须标注证据等级和数据质量
- 支持分层表现模型
- 动态迭代更新
    """,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(projects.router)
app.include_router(outcomes.router)
app.include_router(determinants.router)
app.include_router(kpis.router)
app.include_router(athletes.router)
app.include_router(evidence.router)
app.include_router(reports.router)
app.include_router(agent.router)
app.include_router(literature.router)
app.include_router(performance_model.router)


@app.get("/")
def root():
    return {
        "name": "Project KPI Intelligence Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
