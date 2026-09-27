import json
from pathlib import Path

from fastapi.testclient import TestClient

from psyteardown.api.app import create_app


def test_project_and_initial_intent_round_trip(tmp_path):
    app = create_app(database_path=tmp_path / "product-studio.sqlite3")

    with TestClient(app) as client:
        project_response = client.post(
            "/api/v1/projects",
            headers={"X-Request-ID": "studio-smoke-create"},
            json={
                "name": "Protected focus",
                "collaboration_mode": "managed",
                "actor": "local-user",
                "reason": "Created from Product Studio",
                "created_from": [],
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["project_id"]
        intent_response = client.post(
            f"/api/v1/projects/{project_id}/product-intent/proposals",
            headers={"X-Request-ID": "studio-smoke-intent"},
            json={
                "proposal": {
                    "desired_change": "Protect focused work from avoidable interruption",
                    "affected_people": ["independent knowledge workers"],
                    "current_situation": "Messages arrive across several tools",
                    "explicit_non_goals": [],
                    "known_constraints": [],
                    "resource_preferences": [],
                    "source_refs": [
                        {
                            "source_type": "user_input",
                            "source_id": "studio-input-1",
                        }
                    ],
                },
                "actor": "local-user",
                "reason": "Captured initial intent from Product Studio",
            },
        )

        assert intent_response.status_code == 201
        intent = intent_response.json()
        assert intent["status"] == "proposed"
        intent_id = intent["intent_id"]

        confirmation_response = client.post(
            f"/api/v1/projects/{project_id}/product-intent/{intent_id}/confirmations",
            json={
                "expected_revision": 1,
                "actor": "local-user",
                "reason": "Intent is correct",
            },
        )
        assert confirmation_response.status_code == 201
        assert confirmation_response.json()["status"] == "confirmed"

        correction = {
            "proposal": {
                "desired_change": "Protect focus while preserving urgent contact",
                "affected_people": ["independent knowledge workers"],
                "current_situation": "Messages arrive across several tools",
                "explicit_non_goals": ["block urgent messages"],
                "known_constraints": ["local-first"],
                "resource_preferences": [],
                "source_refs": [
                    {
                        "source_type": "user_input",
                        "source_id": "studio-correction-1",
                    }
                ],
            },
            "intent_id": intent_id,
            "expected_revision": 2,
            "actor": "local-user",
            "reason": "Correct Product Studio understanding",
        }
        correction_response = client.post(
            f"/api/v1/projects/{project_id}/product-intent/proposals",
            json=correction,
        )
        assert correction_response.status_code == 201
        corrected = correction_response.json()
        assert corrected["meta"]["revision"] == 3
        assert corrected["status"] == "proposed"
        assert corrected["confirmation"] is None

        stale_response = client.post(
            f"/api/v1/projects/{project_id}/product-intent/proposals",
            json=correction,
        )
        assert stale_response.status_code == 409
        assert stale_response.json()["error"]["code"] == "revision_conflict"

        view_response = client.get(f"/api/v1/projects/{project_id}")
        assert view_response.status_code == 200
        view = view_response.json()
        assert view["project"]["name"] == "Protected focus"
        assert view["product_intent"]["desired_change"] == (
            "Protect focus while preserving urgent contact"
        )
        assert view["product_intent"]["meta"]["revision"] == 3
        assert view["problem_model"] is None
        assert view["outcome_contract"] is None
        assert view["product_theses"] == []


def test_api_error_keeps_safe_request_id(tmp_path):
    app = create_app(database_path=tmp_path / "product-studio.sqlite3")

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/projects/missing-project",
            headers={"X-Request-ID": "studio-missing-project"},
        )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "studio-missing-project"
    assert response.json()["error"]["request_id"] == "studio-missing-project"


def test_checked_in_openapi_document_matches_application_schema():
    expected = create_app().openapi()
    schema_path = Path(__file__).parents[2] / "studio" / "openapi.json"

    assert json.loads(schema_path.read_text(encoding="utf-8")) == expected


def test_projects_can_be_listed_for_workspace_recovery(tmp_path):
    app = create_app(database_path=tmp_path / "product-studio.sqlite3")
    with TestClient(app) as client:
        for name in ("Older project", "Newer project"):
            response = client.post(
                "/api/v1/projects",
                json={"name": name, "collaboration_mode": "managed", "actor": "local-user", "reason": "start", "created_from": []},
            )
            assert response.status_code == 201
        listed = client.get("/api/v1/projects")
        assert listed.status_code == 200
        assert {item["name"] for item in listed.json()} == {"Newer project", "Older project"}
