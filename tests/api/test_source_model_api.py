from pathlib import Path

from fastapi.testclient import TestClient

import psyteardown.product.generation as generation_module
from psyteardown.api.app import create_app
from psyteardown.product.models import WebProductGenerationContract
from psyteardown.product.source_model import contract_browser_test
from tests.product.source_model_fixtures import ScriptedSourceModel, reference_app, reply_for
from .test_generation_jobs import _confirmed_web_contract


def test_model_generation_is_unavailable_without_a_configured_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("PSYTEARDOWN_PRODUCT_SOURCE_MODEL", raising=False)
    monkeypatch.delenv("PSYTEARDOWN_LLM", raising=False)
    monkeypatch.setenv("PSYTEARDOWN_ENV_FILE", str(tmp_path / "missing.env"))
    with TestClient(create_app(database_path=tmp_path / "product.sqlite3")) as client:
        policy = client.get("/api/v1/source-model-policy").json()
        assert policy["available"] is False
        assert "original user input" in policy["not_sent"]
        assert policy["model_writes"] == ["src/App.tsx", "src/styles.css"]
        assert policy["repair_uses_model"] is False
        project_id, _ = _confirmed_web_contract(client)
        response = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs",
            json={"actor": "user-li", "reason": "model draft", "source": "model"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "domain_gate"


def test_model_job_records_calls_and_serves_the_local_transcript(tmp_path):
    model = ScriptedSourceModel(reply_for("export default function App() { return null; }\n"))
    database = tmp_path / "product.sqlite3"
    with TestClient(create_app(database_path=database, source_model=model)) as client:
        policy = client.get("/api/v1/source-model-policy").json()
        assert policy["available"] is True and policy["provider"] == "scripted"
        project_id, _ = _confirmed_web_contract(client)
        job = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs",
            json={"actor": "user-li", "reason": "model draft", "source": "model"},
        ).json()
        assert job["provider"] == "model_source" and job["budget"]["max_cost_units"] == 2
        run = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs/{job['job_id']}/runs", json={"actor": "local-worker"}
        ).json()
        assert run["status"] == "failed" and run["error_code"] == "model_output_rejected"
        assert run["model_calls"][0]["outcome"] == "rejected"

    with TestClient(create_app(database_path=database, source_model=model)) as restarted:
        base = f"/api/v1/projects/{project_id}/generation-jobs/{job['job_id']}/model-calls"
        transcript = restarted.get(f"{base}/1").json()
        assert transcript["response"].startswith("```tsx")
        assert transcript["gate"]["accepted"] is False
        assert "Confirmed Web generation contract" in transcript["prompt"]
        assert restarted.get(f"{base}/2").status_code == 404


def test_revalidate_saved_rejected_draft_is_local_and_materializes_workspace(tmp_path, monkeypatch):
    model = ScriptedSourceModel()
    database = tmp_path / "product.sqlite3"
    original_check = generation_module.check_model_source
    with TestClient(create_app(database_path=database, source_model=model)) as client:
        project_id, _ = _confirmed_web_contract(client)
        view = client.get(f"/api/v1/projects/{project_id}").json()
        contract_payload = dict(view["web_generation_contract"])
        contract_payload.pop("content_hash", None)
        contract = WebProductGenerationContract.model_validate(contract_payload)
        model.replies.append(reply_for(reference_app(contract)))

        monkeypatch.setattr(
            generation_module,
            "check_model_source",
            lambda files, pinned_contract: ["simulated stale static-gate rule"],
        )
        queued = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs",
            json={"actor": "user-li", "reason": "save model draft", "source": "model"},
        ).json()
        failed = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}/runs",
            json={"actor": "local-worker"},
        ).json()
        assert failed["status"] == "failed"
        assert failed["model_calls"][0]["outcome"] == "rejected"
        assert len(model.calls) == 1

        monkeypatch.setattr(generation_module, "check_model_source", original_check)
        revalidated = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}/revalidations",
            json={"actor": "local-user"},
        )
        assert revalidated.status_code == 200, revalidated.text
        result = revalidated.json()
        assert result["status"] == "succeeded"
        assert result["model_calls"][0]["outcome"] == "rejected"  # Preserve original provider result.
        assert result["model_calls"][0]["static_gate_revalidated"] is True
        assert result["model_calls"][0]["static_gate_version"] == "b7m-static-gate-v3"
        assert result["consumed_cost_units"] == 1  # Local revalidation is not a provider spend.
        assert result["manifest"] is not None
        assert len(model.calls) == 1  # Revalidation must never invoke the provider again.
        source_before_child = client.get(f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}").json()
        source_revision = source_before_child["revision_id"]
        source_workspace = source_before_child["workspace_relative_path"]
        child_response = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}/saved-source-materializations",
            json={"actor": "local-user"},
        )
        assert child_response.status_code == 202, child_response.text
        child_queued = child_response.json()
        assert child_queued["job_id"] != queued["job_id"]
        assert child_queued["materialization_kind"] == "saved_model"
        assert child_queued["source_generation_job_id"] == queued["job_id"]
        assert child_queued["source_generation_job_revision_id"] == source_revision
        assert child_queued["source_response_sha256"] == source_before_child["model_calls"][-1]["response_sha256"]
        child_result = client.post(
            f"/api/v1/projects/{project_id}/generation-jobs/{child_queued['job_id']}/runs",
            json={"actor": "local-worker"},
        )
        assert child_result.status_code == 200, child_result.text
        child = child_result.json()
        assert child["status"] == "succeeded"
        assert child["model_calls"] == []
        assert child["consumed_cost_units"] == 0
        assert child["workspace_relative_path"] != source_workspace
        child_workspace = tmp_path / "workspaces" / child["workspace_relative_path"]
        generated_browser_test = (child_workspace / "tests" / "generated-contract.spec.ts").read_text(encoding="utf-8")
        assert generated_browser_test == contract_browser_test(contract)
        assert "getByRole('button', {name: 'Continue'})" not in generated_browser_test
        assert len(model.calls) == 1
        source_after_child = client.get(f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}").json()
        assert source_after_child["revision_id"] == source_revision
        assert source_after_child["workspace_relative_path"] == source_workspace

        transcript = client.get(
            f"/api/v1/projects/{project_id}/generation-jobs/{queued['job_id']}/model-calls/1"
        ).json()
        assert transcript["gate"]["accepted"] is True
        assert transcript["provider_gate"]["accepted"] is False
        assert transcript["gate_revalidations"][-1]["accepted"] is True
        assert transcript["static_gate_version"] == "b7m-static-gate-v3"
