"""Basic smoke tests for the KPI Agent API."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db


# Use temp file SQLite instead of :memory: to avoid concurrency issues
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
test_engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Import app AFTER setting up test engine so tables go to test DB
from app.main import app
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """Return a TestClient."""
    with TestClient(app) as c:
        yield c


def teardown_module():
    """Clean up temp DB file."""
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except OSError:
        pass


class TestProjectCRUD:
    def test_create_project(self, client):
        resp = client.post("/projects", json={
            "name": "Test 800m Project",
            "sport_type": "Athletics - 800m",
            "project_type": "计量类",
            "level": "精英级",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test 800m Project"

    def test_list_projects(self, client):
        client.post("/projects", json={"name": "P1", "sport_type": "Swimming"})
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_project(self, client):
        client.post("/projects", json={"name": "P2", "sport_type": "Swimming"})
        resp = client.get("/projects/1")
        assert resp.status_code == 200

    def test_update_project(self, client):
        client.post("/projects", json={"name": "P3", "sport_type": "Swimming"})
        resp = client.put("/projects/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_delete_project(self, client):
        client.post("/projects", json={"name": "P4", "sport_type": "Swimming"})
        resp = client.delete("/projects/1")
        assert resp.status_code == 204


class TestOutcomeCRUD:
    def test_create_outcome(self, client):
        client.post("/projects", json={"name": "P", "sport_type": "S"})
        resp = client.post("/outcomes/projects/1", json={
            "name": "800m < 1:48",
            "outcome_type": "成绩",
            "target_value": 108.0,
            "unit": "s",
        })
        assert resp.status_code == 201


class TestAthleteCRUD:
    def test_create_athlete(self, client):
        client.post("/projects", json={"name": "P", "sport_type": "S"})
        resp = client.post("/athletes/projects/1", json={
            "name": "Test Athlete",
            "age": 23, "height": 180, "weight": 70,
        })
        assert resp.status_code == 201

    def test_athlete_dashboard(self, client):
        client.post("/projects", json={"name": "P", "sport_type": "S"})
        client.post("/athletes/projects/1", json={"name": "Test Athlete"})
        resp = client.get("/athletes/1/dashboard")
        assert resp.status_code == 200


class TestAgentWorkflows:
    def _setup(self, client):
        client.post("/projects", json={
            "name": "800m Proj",
            "sport_type": "Athletics - 800m",
            "project_type": "计量类",
            "level": "精英级",
            "target_competition": "Nationals",
        })

    def test_create_project_agent(self, client):
        resp = client.post("/agent/create-project", json={
            "name": "800m Agent Proj",
            "sport_type": "Athletics - 800m",
            "project_type": "计量类",
            "level": "精英级",
        })
        assert resp.status_code == 200
        assert len(resp.json()["missing_info"]) > 0

    def test_define_po(self, client):
        self._setup(client)
        resp = client.post("/agent/define-po", json={
            "project_id": 1,
            "desired_outcome": "800m under 1:48",
            "how_measured": "Electronic timing",
            "target_value_input": 108.0,
            "target_unit": "seconds",
            "baseline_value_input": 114.0,
        })
        assert resp.status_code == 200

    def test_analyze_demands(self, client):
        self._setup(client)
        resp = client.post("/agent/analyze-demands", json={"project_id": 1})
        assert resp.status_code == 200
        assert len(resp.json()["categories"]) >= 6

    def test_build_model(self, client):
        self._setup(client)
        resp = client.post("/agent/build-performance-model", json={"project_id": 1})
        assert resp.status_code == 200
        assert len(resp.json()["determinants_tree"]) > 0

    def test_generate_kpis(self, client):
        self._setup(client)
        client.post("/agent/build-performance-model", json={"project_id": 1})
        resp = client.post("/agent/generate-kpis", json={"project_id": 1})
        assert resp.status_code == 200
        assert resp.json()["kpi_count"] > 0

    def test_full_pipeline(self, client):
        """End-to-end 800m pipeline."""
        client.post("/agent/create-project", json={
            "name": "Full Pipeline",
            "sport_type": "Athletics - 800m",
            "project_type": "计量类",
            "level": "精英级",
        })
        client.post("/agent/define-po", json={
            "project_id": 1,
            "desired_outcome": "800m under 1:48",
            "how_measured": "Official timing",
            "target_value_input": 108.0,
            "target_unit": "seconds",
            "baseline_value_input": 114.0,
        })
        client.post("/athletes/projects/1", json={
            "name": "Runner", "age": 22, "height": 180, "weight": 70, "level": "国家级",
        })
        client.post("/agent/build-performance-model", json={"project_id": 1})
        client.post("/agent/generate-kpis", json={"project_id": 1})

        assert client.post("/agent/evaluate-athlete", json={"athlete_id": 1}).status_code == 200

        resp = client.post("/agent/generate-intervention-plan", json={
            "project_id": 1, "cycle_length_weeks": 12,
        })
        assert resp.status_code == 200
        assert len(resp.json()["interventions"]) > 0

        resp = client.post("/agent/generate-report", json={
            "project_id": 1, "report_type": "PO与KPI设计报告",
        })
        assert resp.status_code == 200

    def test_evaluate_athlete(self, client):
        self._setup(client)
        client.post("/athletes/projects/1", json={"name": "Athlete1"})
        client.post("/agent/build-performance-model", json={"project_id": 1})
        client.post("/agent/generate-kpis", json={"project_id": 1})
        resp = client.post("/agent/evaluate-athlete", json={"athlete_id": 1})
        assert resp.status_code == 200

    def test_generate_report(self, client):
        self._setup(client)
        resp = client.post("/agent/generate-report", json={
            "project_id": 1,
            "report_type": "项目需求分析报告",
        })
        assert resp.status_code == 200


class TestReportTypes:
    def _setup(self, client):
        client.post("/projects", json={"name": "R", "sport_type": "Athletics - 800m"})

    @pytest.mark.parametrize("report_type", [
        "项目需求分析报告",
        "PO与KPI设计报告",
        "KPI趋势报告",
        "干预建议报告",
        "数据质量报告",
        "比赛复盘报告",
    ])
    def test_report_type(self, client, report_type):
        self._setup(client)
        resp = client.post("/agent/generate-report", json={
            "project_id": 1, "report_type": report_type,
        })
        assert resp.status_code == 200
