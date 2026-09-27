from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from psyteardown.api.app import create_app
from psyteardown.product import (
    C1_CONSENT_POLICY_REVISION,
    C1_CONSENT_STATEMENT,
    C1_DATA_CATEGORIES,
    C1_WITHDRAWAL_POLICY,
    InMemoryC1Repository,
    SQLiteC1Repository,
)
from psyteardown.product.c1 import C1ConsentReceipt, C1OutcomeObservation, C1TrialEnvelope, ProductC1ObservationService
from tests.api.test_generation_jobs import _confirmed_web_contract
from tests.api.test_delivery_bundles import _verified_execution


def _confirmed_plan(client: TestClient, project_id: str) -> dict:
    derived = client.post(
        f"/api/v1/projects/{project_id}/outcome-measurement-plan/derive",
        json={"actor": "studio", "reason": "derive C1 plan"},
    ).json()
    proposal = {
        "outcome_contract_revision_id": derived["outcome_contract_revision_id"],
        "measures": [
            {
                key: value
                for key, value in measure.items()
                if key not in {"collectable", "evidence_ceiling"}
            }
            | {"threshold_or_target": "at most 3 observed switches"}
            for measure in derived["measures"]
        ],
        "guardrails": [
            {key: value for key, value in guardrail.items() if key not in {"collectable", "evidence_ceiling"}}
            for guardrail in derived["guardrails"]
        ],
        "stop_condition_ids": derived["stop_condition_ids"],
        "sample_plan": derived["sample_plan"],
        "observation_window": derived["observation_window"],
        "consent_scope": derived["consent_scope"],
        "withdrawal_policy": derived["withdrawal_policy"],
    }
    revised = client.post(
        f"/api/v1/projects/{project_id}/outcome-measurement-plan/proposals",
        json={
            "proposal": proposal,
            "measurement_plan_id": derived["measurement_plan_id"],
            "expected_revision": derived["meta"]["revision"],
            "actor": "test-user",
            "reason": "set C1 threshold",
        },
    )
    assert revised.status_code == 201, revised.text
    confirmed = client.post(
        f"/api/v1/projects/{project_id}/outcome-measurement-plan/{derived['measurement_plan_id']}/confirmations",
        json={
            "expected_revision": revised.json()["meta"]["revision"],
            "actor": "test-user",
            "reason": "confirm C1 plan",
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def _c1_setup(client: TestClient):
    project_id, _ = _confirmed_web_contract(client)
    plan = _confirmed_plan(client, project_id)
    # The helper's contract is confirmed; create an ordinary verified local B6 bundle.
    from tests.api.test_delivery_bundles import _verified_execution
    # _verified_execution creates a new project, so use the same setup steps locally.
    generation = client.post(
        f"/api/v1/projects/{project_id}/generation-jobs",
        json={"actor": "user-li", "reason": "materialize"},
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/generation-jobs/{generation['job_id']}/runs",
        json={"actor": "local-worker"},
    )
    client.app.state.product_execution_job_service.runner = __import__("tests.product.test_delivery", fromlist=["ArtifactRunner"]).ArtifactRunner()
    execution = client.post(
        f"/api/v1/projects/{project_id}/execution-jobs",
        json={"generation_job_id": generation["job_id"], "actor": "user-li", "reason": "validate"},
    ).json()
    executed = client.post(
        f"/api/v1/projects/{project_id}/execution-jobs/{execution['job_id']}/runs",
        json={"actor": "local-worker"},
    ).json()
    assert executed["status"] == "succeeded"
    bundle = client.post(
        f"/api/v1/projects/{project_id}/delivery-bundles",
        json={"execution_job_id": executed["job_id"], "actor": "user-li", "reason": "deliver"},
    ).json()
    contract = client.get(f"/api/v1/projects/{project_id}").json()["web_generation_contract"]
    return project_id, plan, bundle, contract


def test_c1_domain_requires_explicit_consent_and_enforces_source_ceiling():
    repo = InMemoryC1Repository()
    assert repo.list_tombstones() == []
    with pytest.raises(Exception):
        # Smoke the immutable model boundary without pretending a fake plan is an envelope.
        C1ConsentReceipt(
            receipt_id="receipt",
            revision_id="receipt.r1",
            meta={"revision": 1, "created_by": "host", "reason": "test"},
            project_id="project",
            envelope_id="envelope",
            participant_id="participant",
            policy_revision="wrong",
            scope=C1_CONSENT_STATEMENT,
            consented_by="host",
            granted_at="2026-09-26T00:00:00Z",
        )
    assert C1_DATA_CATEGORIES
    assert C1_WITHDRAWAL_POLICY


def test_c1_api_pins_plan_and_delivery_then_withdraws_source_rows(tmp_path):
    database = tmp_path / "product.sqlite3"
    with TestClient(create_app(database_path=database, c1_trial_enabled=True)) as client:
        project_id, plan, bundle, contract = _c1_setup(client)
        start = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes",
            json={
                "measurement_plan_revision_id": plan["revision_id"],
                "delivery_bundle_id": bundle["bundle_id"],
                "execution_job_revision_id": bundle["execution_job_revision_id"],
                "web_generation_contract_revision_id": contract["revision_id"],
                "host": "host-li",
                "actor": "research-lead",
                "reason": "start consented local trial",
            },
        )
        assert start.status_code == 201, start.text
        envelope = start.json()
        policy = client.get("/api/v1/c1-policy")
        assert policy.status_code == 200
        assert policy.json()["consent_policy_revision"] == C1_CONSENT_POLICY_REVISION
        assert policy.json()["evidence_ceiling"] == "observed"

        denied = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants",
            json={
                "consent_policy_revision": C1_CONSENT_POLICY_REVISION,
                "consent_scope_acknowledged": False,
                "actor": "host-li",
                "reason": "declined",
            },
        )
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "domain_gate"

        enrolled = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants",
            json={
                "consent_policy_revision": C1_CONSENT_POLICY_REVISION,
                "consent_scope_acknowledged": True,
                "actor": "host-li",
                "reason": "participant agreed",
            },
        )
        assert enrolled.status_code == 201, enrolled.text
        participant = enrolled.json()["participant"]
        task_id = contract["tasks"][0]["task_id"]
        presentation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/presentations",
            json={"participant_id": participant["participant_id"], "task_id": task_id, "actor": "host-li", "reason": "begin task"},
        )
        assert presentation.status_code == 201, presentation.text
        measure_id = plan["measures"][0]["measure_id"]
        observation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/observations",
            json={
                "participant_id": participant["participant_id"],
                "presentation_id": presentation.json()["presentation_id"],
                "measure_id": measure_id,
                "value": True,
                "status": "observed",
                "actor": "host-li",
                "reason": "manual structured observation",
            },
        )
        assert observation.status_code == 201, observation.text
        assert observation.json()["source_layer"] == "research_observation"
        review = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/reviews",
            json={
                "observation_ids": [observation.json()["observation_id"]],
                "reviewer": "reviewer-li",
                "decision": "accepted",
                "evidence_level_after": "observed",
                "rationale": "reviewed structured task record",
            },
        )
        assert review.status_code == 201, review.text
        assert review.json()["evidence_level_after"] == "observed"
        rejected_promotion = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/reviews",
            json={
                "observation_ids": [observation.json()["observation_id"]],
                "reviewer": "reviewer-li-2",
                "decision": "rejected",
                "evidence_level_after": "observed",
                "rationale": "must remain none",
            },
        )
        assert rejected_promotion.status_code == 409, rejected_promotion.text
        withdrawn = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/withdrawals/{participant['participant_id']}",
            json={"actor": "host-li", "reason": "participant withdrew"},
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["deleted_observations"] == 1
        assert client.get(f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/observations").json() == []

    with TestClient(create_app(database_path=database, c1_trial_enabled=True)) as restarted:
        assert restarted.get(f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/observations").json() == []
        connection = sqlite3.connect(database)
        rows = connection.execute("SELECT object_json FROM c1_records").fetchall()
        audit_rows = connection.execute("SELECT audit_id, details_json FROM c1_audit_events").fetchall()
        connection.close()
        assert all(participant["participant_id"] not in row[0] for row in rows)
        assert all(participant["participant_id"] not in str(row) for row in audit_rows)




def test_c1_trial_is_paused_by_default(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "product.sqlite3")) as client:
        policy = client.get("/api/v1/c1-policy")
        assert policy.status_code == 200
        assert policy.json()["trial_state"] == "paused"
        assert "暂缓" in policy.json()["trial_status_message"]


def test_c1_rejects_placeholder_reviewer(tmp_path):
    database = tmp_path / "product.sqlite3"
    with TestClient(create_app(database_path=database, c1_trial_enabled=True)) as client:
        project_id, plan, bundle, contract = _c1_setup(client)
        envelope = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes",
            json={"measurement_plan_revision_id": plan["revision_id"], "delivery_bundle_id": bundle["bundle_id"], "execution_job_revision_id": bundle["execution_job_revision_id"], "web_generation_contract_revision_id": contract["revision_id"], "host": "host-li", "actor": "host-li", "reason": "start"},
        ).json()
        enrolled = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants",
            json={"consent_policy_revision": "c1-local-v1", "consent_scope_acknowledged": True, "actor": "host-li", "reason": "consent"},
        ).json()
        presentation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/presentations",
            json={"participant_id": enrolled["participant"]["participant_id"], "task_id": contract["tasks"][0]["task_id"], "actor": "host-li", "reason": "present"},
        ).json()
        observation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/observations",
            json={"participant_id": enrolled["participant"]["participant_id"], "presentation_id": presentation["presentation_id"], "measure_id": plan["measures"][0]["measure_id"], "value": True, "status": "observed", "actor": "host-li", "reason": "observe"},
        ).json()
        review = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/reviews",
            json={"observation_ids": [observation["observation_id"]], "reviewer": "named-reviewer", "decision": "accepted", "evidence_level_after": "observed", "rationale": "review"},
        )
        assert review.status_code == 409


@pytest.mark.parametrize("action", ["close", "stop"])
def test_c1_envelope_end_blocks_new_presentations_and_observations(tmp_path, action):
    database = tmp_path / f"{action}.sqlite3"
    with TestClient(create_app(database_path=database, c1_trial_enabled=True)) as client:
        project_id, plan, bundle, contract = _c1_setup(client)
        envelope = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes",
            json={
                "measurement_plan_revision_id": plan["revision_id"],
                "delivery_bundle_id": bundle["bundle_id"],
                "execution_job_revision_id": bundle["execution_job_revision_id"],
                "web_generation_contract_revision_id": contract["revision_id"],
                "host": "host-li",
                "actor": "host-li",
                "reason": "start",
            },
        ).json()
        enrolled = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants",
            json={"consent_policy_revision": C1_CONSENT_POLICY_REVISION, "consent_scope_acknowledged": True, "actor": "host-li", "reason": "consent"},
        ).json()
        existing_presentation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/presentations",
            json={"participant_id": enrolled["participant"]["participant_id"], "task_id": contract["tasks"][0]["task_id"], "actor": "host-li", "reason": "before end"},
        ).json()
        ended = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/{action}",
            json={"actor": "host-li", "reason": f"{action} local trial"},
        )
        assert ended.status_code == 200, ended.text
        assert ended.json()["status"] == ("closed" if action == "close" else "stopped")
        closed_at = datetime.fromisoformat(ended.json()["closed_at"].replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(ended.json()["retention_expires_at"].replace("Z", "+00:00"))
        assert expires_at == closed_at + timedelta(days=30)

        presentation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/presentations",
            json={"participant_id": enrolled["participant"]["participant_id"], "task_id": contract["tasks"][0]["task_id"], "actor": "host-li", "reason": "must be blocked"},
        )
        assert presentation.status_code == 409
        observation = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/observations",
            json={"participant_id": enrolled["participant"]["participant_id"], "presentation_id": existing_presentation["presentation_id"], "measure_id": plan["measures"][0]["measure_id"], "value": True, "status": "observed", "actor": "host-li", "reason": "must be blocked"},
        )
        assert observation.status_code == 409


def test_c1_sqlite_retention_cleanup_runs_on_restart_after_30_days(tmp_path):
    database = tmp_path / "retention.sqlite3"
    current = {"value": datetime(2026, 9, 27, tzinfo=timezone.utc)}

    def clock():
        return current["value"]

    with TestClient(create_app(database_path=database, c1_trial_enabled=True, clock=clock)) as client:
        project_id, plan, bundle, contract = _c1_setup(client)
        envelope = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes",
            json={
                "measurement_plan_revision_id": plan["revision_id"],
                "delivery_bundle_id": bundle["bundle_id"],
                "execution_job_revision_id": bundle["execution_job_revision_id"],
                "web_generation_contract_revision_id": contract["revision_id"],
                "host": "host-li",
                "actor": "host-li",
                "reason": "start",
            },
        ).json()
        enrolled = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants",
            json={"consent_policy_revision": C1_CONSENT_POLICY_REVISION, "consent_scope_acknowledged": True, "actor": "host-li", "reason": "consent"},
        ).json()
        await_close = client.post(
            f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/close",
            json={"actor": "host-li", "reason": "retention test"},
        )
        assert await_close.status_code == 200, await_close.text
        participant_id = enrolled["participant"]["participant_id"]
        current["value"] = datetime(2026, 10, 27, tzinfo=timezone.utc)

    with TestClient(create_app(database_path=database, c1_trial_enabled=True, clock=clock)) as restarted:
        envelopes = restarted.get(f"/api/v1/projects/{project_id}/c1/envelopes")
        assert envelopes.status_code == 200
        assert envelopes.json()[0]["status"] == "closed"
        assert restarted.get(f"/api/v1/projects/{project_id}/c1/envelopes/{envelope['envelope_id']}/participants").json() == []
        connection = sqlite3.connect(database)
        rows = connection.execute("SELECT object_type, object_json FROM c1_records").fetchall()
        connection.close()
        assert [kind for kind, _ in rows] == ["c1_trial_envelope"]
        assert all(participant_id not in payload for _, payload in rows)
