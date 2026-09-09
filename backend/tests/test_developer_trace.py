from fastapi.testclient import TestClient
import pytest

pytest.importorskip("psycopg2")

from app.main import app
from scripts.create_demo_agent_trace import create_demo_agent_trace


client = TestClient(app)


def test_developer_agent_runs_list_api_returns_demo_run():
    run_id = create_demo_agent_trace()

    response = client.get("/api/developer/agent-runs")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["id"] == run_id
    assert data[0]["workflow_name"] == "DemoDeveloperTraceWorkflow"
    assert data[0]["total_steps"] == 4
    assert data[0]["llm_call_count"] >= 1


def test_developer_agent_run_detail_api_returns_full_trace():
    run_id = create_demo_agent_trace()

    response = client.get(f"/api/developer/agent-runs/{run_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == run_id
    assert len(data["steps"]) == 4
    assert data["tool_calls"]
    assert data["llm_calls"]
    assert data["fallback_records"]


def test_developer_agent_steps_api_returns_timeline_fields():
    run_id = create_demo_agent_trace()

    response = client.get(f"/api/developer/agent-runs/{run_id}/steps")

    assert response.status_code == 200
    steps = response.json()["data"]
    assert [step["step_order"] for step in steps] == [1, 2, 3, 4]
    assert steps[1]["provider_name"] == "web_search"
    assert steps[2]["prompt_key"] == "demo_draft_generation"


def test_developer_latest_run_apis_return_latest_demo_run():
    run_id = create_demo_agent_trace()

    latest_response = client.get("/api/developer/latest-run")
    steps_response = client.get("/api/developer/latest-run/steps")

    assert latest_response.status_code == 200
    assert latest_response.json()["data"]["id"] == run_id
    assert steps_response.status_code == 200
    assert steps_response.json()["data"][0]["run_id"] == run_id


def test_developer_trace_returns_mock_provider_and_fallback_flags():
    run_id = create_demo_agent_trace()

    response = client.get(f"/api/developer/agent-runs/{run_id}/steps")
    steps = response.json()["data"]

    assert any(step["is_mock"] for step in steps)
    assert any(step["provider_name"] == "mock" for step in steps)
    assert steps[-1]["fallback_used"] is True
