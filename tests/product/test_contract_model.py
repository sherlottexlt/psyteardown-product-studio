"""Unit tests for C0 real model provider (contract_model.py)."""

from __future__ import annotations

import json

from psyteardown.product.contract_model import (
    OUTCOME_SYSTEM,
    build_intent_prompt,
    parse_intent_reply,
    parse_outcome_reply,
)


def test_parse_intent_reply_valid_json():
    """parse_intent_reply returns ProductIntentProposal for valid JSON."""
    text = json.dumps({
        "desired_change": "Help knowledge workers maintain focus",
        "affected_people": ["remote workers", "freelancers"],
        "current_situation": "Frequent interruptions break concentration",
        "explicit_non_goals": ["employee monitoring"],
        "known_constraints": ["must work offline"],
        "resource_preferences": ["low maintenance"],
    })
    result = parse_intent_reply(text, job_id="test-job")
    # Check it's not a list of errors
    assert not isinstance(result, list)
    assert result.desired_change == "Help knowledge workers maintain focus"
    assert result.affected_people == ["remote workers", "freelancers"]


def test_parse_intent_reply_missing_desired_change():
    """parse_intent_reply rejects JSON without desired_change."""
    text = json.dumps({"affected_people": []})
    result = parse_intent_reply(text, job_id="test-job")
    assert isinstance(result, list)
    assert "desired_change" in result[0]


def test_parse_intent_reply_invalid_json():
    """parse_intent_reply rejects invalid JSON."""
    result = parse_intent_reply("not json", job_id="test-job")
    assert isinstance(result, list)
    assert "not valid JSON" in result[0]


def test_build_intent_prompt():
    """build_intent_prompt includes user input."""
    prompt = build_intent_prompt("Help me focus better")
    assert "Help me focus better" in prompt


def test_thesis_prompt_freezes_realization_mode_allowlist():
    from psyteardown.product.contract_model import THESIS_SYSTEM

    assert '"software", "hardware", "service", "content", "process", "hybrid"' in THESIS_SYSTEM
    assert 'Do not invent values' in THESIS_SYSTEM


def test_outcome_prompt_uses_runtime_severity_enum():
    assert '"hard|strong_avoidance|watch"' in OUTCOME_SYSTEM
    assert 'do not use "soft"' in OUTCOME_SYSTEM


def test_parse_outcome_reply_accepts_runtime_severities(proposed_intent, proposed_problem):
    text = json.dumps({
        "target_segments": ["independent knowledge workers"],
        "applicable_contexts": ["local work"],
        "target_outcomes": [],
        "success_indicators": [],
        "prohibited_outcomes": [
            {
                "prohibited_outcome_id": "no-surveillance",
                "description": "No hidden monitoring",
                "severity": "strong_avoidance",
                "detection_method": "Human review",
                "response": "Stop and reframe",
            },
            {
                "prohibited_outcome_id": "no-pressure",
                "description": "No pressure increase",
                "severity": "watch",
                "detection_method": "User report",
                "response": "Pause",
            },
        ],
        "prohibited_outcomes_reviewed": False,
        "resource_boundary": {"time_budget": "one day"},
        "stop_conditions": [],
        "minimum_delivery_maturity": "runnable_prototype",
        "required_real_world_evidence": [],
    })
    result = parse_outcome_reply(text, job_id="outcome-job", intent=proposed_intent, problem=proposed_problem)
    assert not isinstance(result, list)
    assert [item.severity for item in result.prohibited_outcomes] == ["strong_avoidance", "watch"]


def test_parse_outcome_reply_keeps_legacy_soft_as_strong_avoidance(proposed_intent, proposed_problem):
    text = json.dumps({
        "prohibited_outcomes": [{
            "prohibited_outcome_id": "legacy",
            "description": "Legacy label",
            "severity": "soft",
            "detection_method": "Human review",
            "response": "Pause",
        }],
        "resource_boundary": {"time_budget": "one day"},
    })
    result = parse_outcome_reply(text, job_id="legacy-job", intent=proposed_intent, problem=proposed_problem)
    assert not isinstance(result, list)
    assert result.prohibited_outcomes[0].severity == "strong_avoidance"
