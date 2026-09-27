from fastapi.testclient import TestClient

from psyteardown.api.app import create_app
from .payloads import contract_proposal, intent_proposal, problem_proposal


def _confirmed_intent(client: TestClient) -> tuple[str, dict]:
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Focus boundary",
            "collaboration_mode": "managed",
            "actor": "user-li",
            "reason": "start project",
            "created_from": [],
        },
    )
    project_id = project_response.json()["project_id"]
    intent_response = client.post(
        f"/api/v1/projects/{project_id}/product-intent/proposals",
        json={
            "proposal": intent_proposal(),
            "actor": "user-li",
            "reason": "capture intent",
        },
    )
    draft = intent_response.json()
    confirmation = client.post(
        f"/api/v1/projects/{project_id}/product-intent/{draft['intent_id']}/confirmations",
        json={
            "expected_revision": 1,
            "actor": "user-li",
            "reason": "intent is correct",
        },
    )
    assert confirmation.status_code == 201
    return project_id, confirmation.json()


def test_one_raw_input_is_persisted_before_intent_proposal(tmp_path):
    database = tmp_path / "product-studio.sqlite3"
    raw_input = "I want my workday to feel less fragmented"
    with TestClient(create_app(database_path=database)) as client:
        project_response = client.post(
            "/api/v1/projects",
            json={
                "name": "Incomplete idea",
                "collaboration_mode": "managed",
                "actor": "user-li",
                "reason": "start",
                "created_from": [],
            },
        )
        project_id = project_response.json()["project_id"]
        queued_response = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={
                "kind": "product_intent",
                "raw_input": raw_input,
                "actor": "user-li",
                "reason": "structure raw input",
            },
        )
        assert queued_response.status_code == 202
        queued = queued_response.json()
        assert queued["raw_input"] == raw_input
        assert client.get(f"/api/v1/projects/{project_id}").json()["product_intent"] is None

    with TestClient(create_app(database_path=database)) as restarted:
        recovered = restarted.get(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}"
        ).json()
        assert recovered["status"] == "queued"
        assert recovered["raw_input"] == raw_input
        completed = restarted.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert completed.json()["status"] == "succeeded"
        intent = restarted.get(f"/api/v1/projects/{project_id}").json()["product_intent"]
        assert intent["status"] == "proposed"
        assert intent["source_refs"][0]["locator"] == "product_proposal_job.raw_input"


def test_jobs_persist_before_run_and_recover_after_restart(tmp_path):
    database = tmp_path / "product-studio.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        project_id, _ = _confirmed_intent(client)
        queued_response = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={
                "kind": "problem_model",
                "actor": "user-li",
                "reason": "generate a problem proposal",
            },
        )
        assert queued_response.status_code == 202
        queued = queued_response.json()
        assert queued["status"] == "queued"
        assert queued["attempt"] == 0
        assert client.get(f"/api/v1/projects/{project_id}").json()["problem_model"] is None

        run_response = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert run_response.status_code == 200
        completed = run_response.json()
        assert completed["status"] == "succeeded"
        problem = client.get(f"/api/v1/projects/{project_id}").json()["problem_model"]
        assert problem["status"] == "proposed"
        assert completed["result_revision_id"] == problem["revision_id"]

    with TestClient(create_app(database_path=database)) as restarted:
        job_response = restarted.get(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}"
        )
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "succeeded"
        view = restarted.get(f"/api/v1/projects/{project_id}").json()
        assert view["product_intent"]["status"] == "confirmed"
        assert view["problem_model"]["status"] == "proposed"


def test_stale_pinned_input_prevents_job_result_commit(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "product-studio.sqlite3")
    ) as client:
        project_id, intent = _confirmed_intent(client)
        queued = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={
                "kind": "problem_model",
                "actor": "user-li",
                "reason": "generate",
            },
        ).json()
        corrected_payload = intent_proposal()
        corrected_payload["current_situation"] = "The context changed before execution"
        correction = client.post(
            f"/api/v1/projects/{project_id}/product-intent/proposals",
            json={
                "proposal": corrected_payload,
                "intent_id": intent["intent_id"],
                "expected_revision": intent["meta"]["revision"],
                "actor": "user-li",
                "reason": "correct context",
            },
        )
        assert correction.status_code == 201

        run = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}/runs",
            json={"actor": "local-worker"},
        )

        assert run.status_code == 200
        assert run.json()["status"] == "stale_input"
        assert client.get(f"/api/v1/projects/{project_id}").json()["problem_model"] is None


def test_outcome_job_keeps_human_confirmation_gate(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "product-studio.sqlite3")
    ) as client:
        project_id, _ = _confirmed_intent(client)
        problem_job = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={"kind": "problem_model", "actor": "user-li", "reason": "generate"},
        ).json()
        client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{problem_job['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        problem = client.get(f"/api/v1/projects/{project_id}").json()["problem_model"]
        confirmed_problem = client.post(
            f"/api/v1/projects/{project_id}/problem-model/{problem['problem_model_id']}/confirmations",
            json={
                "expected_revision": problem["meta"]["revision"],
                "actor": "user-li",
                "reason": "problem framing is acceptable",
            },
        )
        assert confirmed_problem.status_code == 201

        outcome_job = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={
                "kind": "outcome_contract",
                "actor": "user-li",
                "reason": "generate contract",
            },
        ).json()
        completed = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{outcome_job['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert completed.json()["status"] == "succeeded"
        contract = client.get(f"/api/v1/projects/{project_id}").json()["outcome_contract"]
        assert contract["status"] == "proposed"
        assert contract["prohibited_outcomes_reviewed"] is False

        blocked = client.post(
            f"/api/v1/projects/{project_id}/outcome-contract/{contract['outcome_contract_id']}/confirmations",
            json={
                "expected_revision": contract["meta"]["revision"],
                "actor": "user-li",
                "reason": "attempt to bypass review",
            },
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "domain_validation_error"


def test_product_theses_job_returns_three_comparable_candidates(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "product-studio.sqlite3")
    ) as client:
        project_id, intent = _confirmed_intent(client)
        problem_job = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={"kind": "problem_model", "actor": "user-li", "reason": "generate"},
        ).json()
        problem_run = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{problem_job['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert problem_run.json()["status"] == "succeeded"
        problem = client.get(f"/api/v1/projects/{project_id}").json()["problem_model"]
        problem_confirmation = client.post(
            f"/api/v1/projects/{project_id}/problem-model/{problem['problem_model_id']}/confirmations",
            json={
                "expected_revision": problem["meta"]["revision"],
                "actor": "user-li",
                "reason": "problem framing is acceptable",
            },
        )
        assert problem_confirmation.status_code == 201
        problem = problem_confirmation.json()

        contract_response = client.post(
            f"/api/v1/projects/{project_id}/outcome-contract/proposals",
            json={
                "proposal": contract_proposal(intent["revision_id"], problem["revision_id"]),
                "actor": "studio",
                "reason": "define outcome boundary",
            },
        )
        assert contract_response.status_code == 201
        contract = contract_response.json()
        contract_confirmation = client.post(
            f"/api/v1/projects/{project_id}/outcome-contract/{contract['outcome_contract_id']}/confirmations",
            json={
                "expected_revision": contract["meta"]["revision"],
                "actor": "user-li",
                "reason": "outcome and harm boundaries are acceptable",
            },
        )
        assert contract_confirmation.status_code == 201

        queued_response = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={
                "kind": "product_theses",
                "actor": "user-li",
                "reason": "search differentiated product paths",
            },
        )
        assert queued_response.status_code == 202
        queued = queued_response.json()
        assert len(queued["result_object_ids"]) == 3

        completed = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert completed.status_code == 200
        payload = completed.json()
        assert payload["status"] == "succeeded"
        assert len(payload["result_revision_ids"]) == 3
        view = client.get(f"/api/v1/projects/{project_id}").json()
        assert len(view["product_theses"]) == 3
        assert len({item["name"] for item in view["product_theses"]}) == 3
        assert len({item["differentiation"] for item in view["product_theses"]}) == 3

        selected = view["product_theses"][1]
        transitioned = client.post(
            f"/api/v1/projects/{project_id}/product-theses/{selected['thesis_id']}/transitions",
            json={
                "expected_revision": selected["meta"]["revision"],
                "to_status": "selected",
                "actor": "user-li",
                "actor_type": "human",
                "reason": "select this path for the next low-cost slice",
                "authorization_ref": None,
            },
        )
        assert transitioned.status_code == 201
        assert transitioned.json()["status"] == "selected"


def test_web_generation_contract_job_exposes_b2_template_boundary(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "product-studio.sqlite3")
    ) as client:
        project_id, intent = _confirmed_intent(client)
        problem_job = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={"kind": "problem_model", "actor": "user-li", "reason": "generate"},
        ).json()
        client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{problem_job['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        problem = client.get(f"/api/v1/projects/{project_id}").json()["problem_model"]
        confirmed_problem = client.post(
            f"/api/v1/projects/{project_id}/problem-model/{problem['problem_model_id']}/confirmations",
            json={"expected_revision": problem["meta"]["revision"], "actor": "user-li", "reason": "review"},
        ).json()
        contract_response = client.post(
            f"/api/v1/projects/{project_id}/outcome-contract/proposals",
            json={
                "proposal": contract_proposal(intent["revision_id"], confirmed_problem["revision_id"]),
                "actor": "studio", "reason": "define outcome",
            },
        ).json()
        confirmed_contract = client.post(
            f"/api/v1/projects/{project_id}/outcome-contract/{contract_response['outcome_contract_id']}/confirmations",
            json={"expected_revision": contract_response["meta"]["revision"], "actor": "user-li", "reason": "review boundary"},
        ).json()
        thesis_job = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={"kind": "product_theses", "actor": "user-li", "reason": "search"},
        ).json()
        client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{thesis_job['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        thesis = client.get(f"/api/v1/projects/{project_id}").json()["product_theses"][0]
        exploring = client.post(
            f"/api/v1/projects/{project_id}/product-theses/{thesis['thesis_id']}/transitions",
            json={
                "expected_revision": thesis["meta"]["revision"],
                "to_status": "exploring", "actor": "user-li", "actor_type": "human", "reason": "authorize exploration", "authorization_ref": None,
            },
        ).json()
        queued = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs",
            json={"kind": "web_generation_contract", "actor": "user-li", "reason": "describe Web realization"},
        )
        assert queued.status_code == 202
        completed = client.post(
            f"/api/v1/projects/{project_id}/proposal-jobs/{queued.json()['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert completed.status_code == 200
        view = client.get(f"/api/v1/projects/{project_id}").json()
        generation = view["web_generation_contract"]
        assert completed.json()["status"] == "succeeded"
        assert generation["status"] == "proposed"
        assert generation["template_id"] == "react_typescript_vite_spa"
        assert generation["network_policy"] == "none"
        assert generation["data_policy"] == "local_fixture_only"
        assert generation["product_thesis_revision_id"] == exploring["revision_id"]
        assert len(generation["acceptance_checks"]) >= 3


def test_raw_input_is_bounded_before_it_is_persisted(tmp_path):
    app = create_app(database_path=tmp_path / "product-studio.sqlite3")
    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"name": "Bounded input", "collaboration_mode": "managed", "actor": "local-user", "reason": "start", "created_from": []},
        ).json()
        response = client.post(
            f"/api/v1/projects/{project['project_id']}/proposal-jobs",
            json={"kind": "product_intent", "raw_input": "x" * 4001, "actor": "local-user", "reason": "too large"},
        )
        assert response.status_code == 422
        assert client.get(f"/api/v1/projects/{project['project_id']}/proposal-jobs").json() == []
