"""Real model provider for Product Contract proposals (ProductIntent, ProblemModel, OutcomeContract, ProductThesis).

Following C0 decisions (PS-O017/O018/O019):
- Full confirmed upstream objects + user input sent to provider
- Transcript saved locally outside workspace, not in delivery bundle
- Max 2 calls per object (same as B7m)
- No automatic retry on failure
- No monetary budget tracking (call count only)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psyteardown.product.commands import (
    OutcomeContractProposal,
    ProblemModelProposal,
    ProductIntentProposal,
    ProductThesisProposal,
)
from psyteardown.product.models import (
    OutcomeContract,
    ProblemModel,
    ProductIntent,
    ProductThesis,
)
from psyteardown.product.env import get_project_env

CONTRACT_MODEL_MAX_OUTPUT_TOKENS = 8000
CONTRACT_MODEL_MAX_CALLS_PER_JOB = 2


class ContractModelError(RuntimeError):
    """The provider call failed; the message is safe to show."""


@dataclass(frozen=True)
class ContractModelReply:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    truncated: bool = False


class ProductContractModel(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, prompt: str) -> ContractModelReply: ...


class DeepSeekProductContractModel:
    """OpenAI-compatible DeepSeek chat call for Product Contract proposals."""

    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 240,
    ) -> None:
        key = api_key or get_project_env("DEEPSEEK_API_KEY")
        if not key:
            raise ContractModelError("DEEPSEEK_API_KEY is not configured")
        self._key = key
        self.model = model or get_project_env("DEEPSEEK_MODEL") or "deepseek-chat"
        self._base_url = (base_url or get_project_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self._timeout = timeout_seconds
        # Reasoning models can spend the whole output budget thinking
        self._thinking = get_project_env("DEEPSEEK_THINKING", "disabled").strip().lower() == "enabled"

    def generate(self, *, system: str, prompt: str) -> ContractModelReply:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": CONTRACT_MODEL_MAX_OUTPUT_TOKENS,
            "temperature": 0.3,
            # Contract proposals are parsed as JSON locally. DeepSeek's
            # reasoning-capable models may otherwise put reasoning or prose in
            # the visible content even when the prompt asks for JSON only.
            "response_format": {"type": "json_object"},
            "thinking": {"type": "enabled" if self._thinking else "disabled"},
        }
        request = Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"},
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ContractModelError(f"model provider returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ContractModelError("model provider could not be reached") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractModelError("model provider returned invalid JSON") from exc
        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ContractModelError("model provider response had no message content") from exc
        if not isinstance(text, str):
            raise ContractModelError("model provider message content was not text")
        usage = payload.get("usage") or {}
        return ContractModelReply(
            text=text or "",
            model=str(payload.get("model") or self.model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            truncated=choice.get("finish_reason") == "length",
        )


def build_contract_model_from_env() -> ProductContractModel | None:
    """Opt-in: only PSYTEARDOWN_PRODUCT_CONTRACT_MODEL=deepseek enables a real model."""
    provider = get_project_env("PSYTEARDOWN_PRODUCT_CONTRACT_MODEL") or get_project_env("PSYTEARDOWN_LLM", "")
    if provider.strip().lower() != "deepseek":
        return None
    try:
        return DeepSeekProductContractModel()
    except ContractModelError:
        return None


# System prompts and parsing functions for each contract type will be added below

INTENT_SYSTEM = """You are helping structure a user's initial product idea into a ProductIntent.

The ProductIntent captures:
- desired_change: what the user wants to be different
- affected_people: who experiences the current situation
- current_situation: the context or problem as it exists now
- explicit_non_goals: what this product deliberately will NOT do
- known_constraints: limits the user has stated (time, privacy, cost, etc.)
- resource_preferences: user's stated preferences about effort or resources

Output valid JSON matching this schema:
{
  "desired_change": "string",
  "affected_people": ["string"],
  "current_situation": "string",
  "explicit_non_goals": ["string"],
  "known_constraints": ["string"],
  "resource_preferences": ["string"]
}

Rules:
- Be concrete and specific; avoid vague marketing language
- If the user hasn't stated something, use an empty array [] or empty string ""
- affected_people should be concrete roles or groups, not "users" or "people"
- explicit_non_goals captures what the user said they DON'T want, not inferred negations
- Keep each field focused; don't repeat the same information across fields
"""


PROBLEM_SYSTEM = """You are helping structure a ProblemModel from a confirmed ProductIntent.

The ProblemModel captures:
- facts: observable, sourced statements about the current situation
- assumptions: things we're taking as given but haven't verified
- unknowns: critical questions that could change the approach
- competing_explanations: at least 2 different reasons why the problem might exist
- stakeholder_tensions: conflicting needs between different affected groups

Output valid JSON matching this schema:
{
  "facts": [{"fact_id": "unique-id", "statement": "string", "source_refs": []}],
   "assumptions": [{"assumption_id": "unique-id", "statement": "string", "consequence_if_wrong": "string", "cheapest_validation": "string"}],
  "unknowns": [{"unknown_id": "unique-id", "question": "string", "decision_impact": "string", "next_step": "string"}],
  "competing_explanations": [{"explanation_id": "unique-id", "statement": "string", "supporting_fact_ids": ["fact-id"], "cheapest_falsification": "string"}],
   "stakeholder_tensions": [{"tension_id": "unique-id", "stakeholder_refs": ["group1", "group2"], "description": "string", "unresolved_value_choice": "string"}]
}

Rules:
- Must provide at least 2 competing_explanations (different root causes)
- Each explanation must reference at least one fact_id
- unknowns should be questions that would change the product approach, not just nice-to-know
- Use kebab-case IDs
- Keep it concrete and falsifiable
"""


OUTCOME_SYSTEM = """You are helping structure an OutcomeContract from a confirmed ProductIntent and ProblemModel.

The OutcomeContract captures:
- target_segments: who will use this product
- applicable_contexts: when/where it applies
- target_outcomes: what changes we're aiming for
- success_indicators: how we'll measure success
- prohibited_outcomes: what must NOT happen
- resource_boundary: limits on time, cost, data, maintenance
- stop_conditions: when to halt or reframe

Output valid JSON matching this schema:
{
  "target_segments": ["string"],
  "applicable_contexts": ["string"],
  "target_outcomes": [{"outcome_id": "id", "description": "string", "indicator_ids": ["indicator-id"]}],
  "success_indicators": [{"indicator_id": "id", "operational_definition": "string", "observation_method": "string", "desired_direction": "string", "threshold_or_target": "string", "required_evidence": "string"}],
  "prohibited_outcomes": [{"prohibited_outcome_id": "id", "description": "string", "severity": "hard|strong_avoidance|watch", "detection_method": "string", "response": "string"}],
  "prohibited_outcomes_reviewed": false,
   "resource_boundary": {"time_budget": "string or null", "economic_budget": "string or null", "data_boundary": "string or null", "maintenance_budget": "string or null", "explicit_unknowns": ["string"]},
   "stop_conditions": [{"condition_id": "id", "condition": "string", "action": "pause|stop|reframe|escalate"}],
  "minimum_delivery_maturity": "runnable_prototype",
  "required_real_world_evidence": ["string"]
}

Rules:
- success_indicators must be observable and measurable
- required_evidence should be "real_user_observation" for outcome claims
- prohibited_outcomes must include explicit_non_goals from Intent
- severity must be exactly one of "hard", "strong_avoidance", or "watch"; do not use "soft"
- Leave threshold_or_target as "Must be set by a human before confirmation" if not specified
- minimum_delivery_maturity for first slice is "runnable_prototype"
"""


THESIS_SYSTEM = """You are helping generate 3 ProductThesis candidates from a confirmed ProblemModel and OutcomeContract.

Each ProductThesis is a distinct product approach with different mechanisms, risks, and validation strategies.

Output valid JSON with exactly 3 theses matching this schema:
{
  "theses": [
    {
      "name": "Short descriptive name",
      "product_promise": "What this product will do for the user",
      "differentiation": "How this differs from other approaches",
      "realization_modes": ["software"],
      "mechanism_hypotheses": [{"mechanism_id": "id", "condition": "string", "proposed_intervention": "string", "expected_change": "string", "uncertainty": "string"}],
      "falsifiable_predictions": [{"prediction_id": "id", "prediction": "string", "failure_observation": "string", "cheapest_test": "string"}],
       "validation_strategy": [{"validation_step_id": "id", "question": "string", "method": "string", "evidence_level": "deterministic_check|simulation|expert_review|real_user_observation|operational_result", "pass_condition": "string", "estimated_cost": "string"}],
      "key_unknowns": ["string"],
      "key_risks": ["string"],
      "delivery_estimate": {"initial_delivery_cost": "string", "operating_cost": "string", "maintenance_burden": "string"}
    }
  ]
}

Rules:
- realization_modes must contain only exact values from this allowlist: "software", "hardware", "service", "content", "process", "hybrid". Do not invent values such as "mobile", "desktop", "app", or "digital"; for this first slice, use ["software"] unless the thesis genuinely requires another approved mode.
- Each thesis must have meaningfully different mechanisms (not just UI variations)
- mechanism_hypotheses explain the causal theory
- falsifiable_predictions must be testable and specify what failure looks like
- validation_strategy evidence_level must be one of: "deterministic_check", "simulation", "expert_review", "real_user_observation", "operational_result"
- Theses should vary in cost, risk, and unknowns
- Keep delivery_estimate concrete and realistic
"""


def parse_intent_reply(text: str, *, job_id: str) -> ProductIntentProposal | list[str]:
    """Parse JSON ProductIntent from model reply; returns proposal or rejection reasons."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return ["response was not valid JSON"]

    # Validate required fields
    if not isinstance(data.get("desired_change"), str) or not data["desired_change"].strip():
        return ["desired_change must be a non-empty string"]
    if not isinstance(data.get("affected_people"), list):
        return ["affected_people must be an array"]
    if not isinstance(data.get("current_situation"), str):
        return ["current_situation must be a string"]

    # Build proposal
    from psyteardown.product.models import SourceReference

    return ProductIntentProposal(
        desired_change=data["desired_change"].strip(),
        affected_people=[str(p).strip() for p in data.get("affected_people", []) if str(p).strip()],
        current_situation=data.get("current_situation", "").strip() or None,
        explicit_non_goals=[str(g).strip() for g in data.get("explicit_non_goals", []) if str(g).strip()],
        known_constraints=[str(c).strip() for c in data.get("known_constraints", []) if str(c).strip()],
        resource_preferences=[str(r).strip() for r in data.get("resource_preferences", []) if str(r).strip()],
        source_refs=[
            SourceReference(
                source_type="model_proposal",
                source_id=job_id,
                revision_id="c0-deepseek-v1",
            )
        ],
    )


def build_intent_prompt(raw_input: str) -> str:
    """Build prompt for ProductIntent generation."""
    return f"""User input:
{raw_input}

Generate a ProductIntent JSON that structures this input."""


def parse_problem_reply(text: str, *, job_id: str, intent: ProductIntent) -> ProblemModelProposal | list[str]:
    """Parse JSON ProblemModel from model reply; returns proposal or rejection reasons."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return ["response was not valid JSON"]

    # Validate competing explanations requirement
    explanations = data.get("competing_explanations", [])
    if not isinstance(explanations, list) or len(explanations) < 2:
        return ["must provide at least 2 competing_explanations"]

    from psyteardown.product.models import (
        CompetingExplanation,
        ProblemAssumption,
        ProblemFact,
        ProblemUnknown,
        SourceReference,
        StakeholderTension,
    )

    # Build facts
    facts = []
    for f in data.get("facts", []):
        if not isinstance(f, dict) or not f.get("fact_id") or not f.get("statement"):
            return ["each fact must have fact_id and statement"]
        facts.append(
            ProblemFact(
                fact_id=str(f["fact_id"]),
                statement=str(f["statement"]),
                source_refs=intent.source_refs,
            )
        )

    # Build assumptions
    assumptions = []
    for a in data.get("assumptions", []):
        if isinstance(a, dict) and a.get("assumption_id") and a.get("statement"):
            assumptions.append(
                ProblemAssumption(
                    assumption_id=str(a["assumption_id"]),
                    statement=str(a["statement"]),
                    consequence_if_wrong=str(a.get("consequence_if_wrong", "")),
                    cheapest_validation=str(a.get("cheapest_validation", "")),
                )
            )

    # Build unknowns
    unknowns = []
    for u in data.get("unknowns", []):
        if isinstance(u, dict) and u.get("unknown_id") and u.get("question"):
            unknowns.append(
                ProblemUnknown(
                    unknown_id=str(u["unknown_id"]),
                    question=str(u["question"]),
                    decision_impact=str(u.get("decision_impact", "")),
                    next_step=str(u.get("next_step", "")),
                )
            )

    # Build competing explanations
    competing = []
    for e in explanations:
        if not isinstance(e, dict) or not e.get("explanation_id") or not e.get("statement"):
            return ["each competing_explanation must have explanation_id and statement"]
        competing.append(
            CompetingExplanation(
                explanation_id=str(e["explanation_id"]),
                statement=str(e["statement"]),
                supporting_fact_ids=tuple(str(fid) for fid in e.get("supporting_fact_ids", [])),
                cheapest_falsification=str(e.get("cheapest_falsification", "")),
            )
        )

    # Build stakeholder tensions
    tensions = []
    for t in data.get("stakeholder_tensions", []):
        if isinstance(t, dict) and t.get("tension_id") and t.get("description"):
            tensions.append(
                StakeholderTension(
                    tension_id=str(t["tension_id"]),
                    stakeholder_refs=tuple(str(g) for g in t.get("stakeholder_refs", [])),
                    description=str(t["description"]),
                    unresolved_value_choice=str(t.get("unresolved_value_choice", "")),
                )
            )

    return ProblemModelProposal(
        intent_revision_id=intent.revision_id,
        facts=facts,
        assumptions=assumptions,
        unknowns=unknowns,
        competing_explanations=competing,
        stakeholder_tensions=tensions,
    )


def build_problem_prompt(intent: ProductIntent) -> str:
    """Build prompt for ProblemModel generation."""
    return f"""Confirmed ProductIntent:
{json.dumps({
    "desired_change": intent.desired_change,
    "affected_people": intent.affected_people,
    "current_situation": intent.current_situation,
    "explicit_non_goals": intent.explicit_non_goals,
    "known_constraints": intent.known_constraints,
}, ensure_ascii=False, indent=2)}

Generate a ProblemModel JSON that explores this problem space with at least 2 competing explanations."""


def _normalize_prohibited_outcome_severity(value: object) -> str:
    """Normalize the one legacy label emitted by older C0 prompts.

    The domain model deliberately exposes the more precise three-level vocabulary.
    Accepting the old ``soft`` spelling at the parser boundary lets an already
    queued provider response be reviewed and retried without weakening the stored
    contract schema.
    """
    normalized = str(value or "hard").strip().lower()
    return "strong_avoidance" if normalized == "soft" else normalized


def parse_outcome_reply(
    text: str, *, job_id: str, intent: ProductIntent, problem: ProblemModel
) -> OutcomeContractProposal | list[str]:
    """Parse JSON OutcomeContract from model reply; returns proposal or rejection reasons."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return ["response was not valid JSON"]

    from psyteardown.product.models import (
        DeliveryMaturity,
        ProhibitedOutcome,
        ResourceBoundary,
        StopCondition,
        SuccessIndicator,
        TargetOutcome,
    )

    # Build target outcomes
    target_outcomes = []
    for t in data.get("target_outcomes", []):
        if isinstance(t, dict) and t.get("outcome_id") and t.get("description"):
            target_outcomes.append(
                TargetOutcome(
                    outcome_id=str(t["outcome_id"]),
                    description=str(t["description"]),
                    indicator_ids=tuple(str(iid) for iid in t.get("indicator_ids", [])),
                )
            )

    # Build success indicators
    indicators = []
    for i in data.get("success_indicators", []):
        if isinstance(i, dict) and i.get("indicator_id") and i.get("operational_definition"):
            indicators.append(
                SuccessIndicator(
                    indicator_id=str(i["indicator_id"]),
                    operational_definition=str(i["operational_definition"]),
                    observation_method=str(i.get("observation_method", "")),
                    desired_direction=str(i.get("desired_direction", "")),
                    threshold_or_target=str(i.get("threshold_or_target", "")),
                    required_evidence=str(i.get("required_evidence", "real_user_observation")),
                )
            )

    # Build prohibited outcomes
    prohibited = []
    for p in data.get("prohibited_outcomes", []):
        if isinstance(p, dict) and p.get("prohibited_outcome_id") and p.get("description"):
            prohibited.append(
                ProhibitedOutcome(
                    prohibited_outcome_id=str(p["prohibited_outcome_id"]),
                    description=str(p["description"]),
                    severity=_normalize_prohibited_outcome_severity(p.get("severity", "hard")),
                    detection_method=str(p.get("detection_method", "")),
                    response=str(p.get("response", "")),
                )
            )

    # Build resource boundary
    rb_data = data.get("resource_boundary", {})
    resource_boundary = ResourceBoundary(
        time_budget=rb_data.get("time_budget"),
        economic_budget=rb_data.get("economic_budget"),
        data_boundary=rb_data.get("data_boundary"),
        maintenance_budget=rb_data.get("maintenance_budget"),
        explicit_unknowns=tuple(str(u) for u in rb_data.get("explicit_unknowns", [])),
    )

    # Build stop conditions
    stop_conditions = []
    for s in data.get("stop_conditions", []):
        if isinstance(s, dict) and s.get("condition_id") and s.get("condition"):
            stop_conditions.append(
                StopCondition(
                    condition_id=str(s["condition_id"]),
                    condition=str(s["condition"]),
                    action=str(s.get("action", "reframe")),
                )
            )

    return OutcomeContractProposal(
        intent_revision_id=intent.revision_id,
        problem_model_revision_id=problem.revision_id,
        target_segments=data.get("target_segments", []),
        applicable_contexts=data.get("applicable_contexts", []),
        target_outcomes=target_outcomes,
        success_indicators=indicators,
        prohibited_outcomes=prohibited,
        prohibited_outcomes_reviewed=data.get("prohibited_outcomes_reviewed", False),
        resource_boundary=resource_boundary,
        stop_conditions=stop_conditions,
        minimum_delivery_maturity=DeliveryMaturity.RUNNABLE_PROTOTYPE,
        required_real_world_evidence=data.get("required_real_world_evidence", []),
    )


def build_outcome_prompt(intent: ProductIntent, problem: ProblemModel) -> str:
    """Build prompt for OutcomeContract generation."""
    return f"""Confirmed ProductIntent:
{json.dumps({
    "desired_change": intent.desired_change,
    "affected_people": intent.affected_people,
    "explicit_non_goals": intent.explicit_non_goals,
}, ensure_ascii=False, indent=2)}

Confirmed ProblemModel:
{json.dumps({
    "facts": [{"fact_id": f.fact_id, "statement": f.statement} for f in problem.facts],
    "competing_explanations": [{"explanation_id": e.explanation_id, "statement": e.statement} for e in problem.competing_explanations],
}, ensure_ascii=False, indent=2)}

Generate an OutcomeContract JSON that defines measurable success criteria."""


def parse_theses_reply(
    text: str, *, job_id: str, problem: ProblemModel, contract: OutcomeContract
) -> tuple[ProductThesisProposal, ...] | list[str]:
    """Parse JSON theses from model reply; returns 3 proposals or rejection reasons."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return ["response was not valid JSON"]

    theses_data = data.get("theses", [])
    if not isinstance(theses_data, list) or len(theses_data) != 3:
        return ["must provide exactly 3 theses"]

    from psyteardown.product.models import (
        DeliveryEstimate,
        FalsifiablePrediction,
        MechanismHypothesis,
        SourceReference,
        ValidationStep,
    )

    source = SourceReference(
        source_type="model_proposal",
        source_id=job_id,
        revision_id="c0-deepseek-v1",
    )

    proposals = []
    for t in theses_data:
        if not isinstance(t, dict) or not t.get("name") or not t.get("product_promise"):
            return ["each thesis must have name and product_promise"]

        # Build mechanism hypotheses
        mechanisms = []
        for m in t.get("mechanism_hypotheses", []):
            if isinstance(m, dict) and m.get("mechanism_id"):
                mechanisms.append(
                    MechanismHypothesis(
                        mechanism_id=str(m["mechanism_id"]),
                        condition=str(m.get("condition", "")),
                        proposed_intervention=str(m.get("proposed_intervention", "")),
                        expected_change=str(m.get("expected_change", "")),
                        uncertainty=str(m.get("uncertainty", "")),
                        evidence_refs=(source,),
                    )
                )

        # Build falsifiable predictions
        predictions = []
        for p in t.get("falsifiable_predictions", []):
            if isinstance(p, dict) and p.get("prediction_id"):
                predictions.append(
                    FalsifiablePrediction(
                        prediction_id=str(p["prediction_id"]),
                        prediction=str(p.get("prediction", "")),
                        failure_observation=str(p.get("failure_observation", "")),
                        cheapest_test=str(p.get("cheapest_test", "")),
                    )
                )

        # Build validation strategy
        validation = []
        for v in t.get("validation_strategy", []):
            if isinstance(v, dict) and v.get("validation_step_id"):
                validation.append(
                    ValidationStep(
                        validation_step_id=str(v["validation_step_id"]),
                        question=str(v.get("question", "")),
                        method=str(v.get("method", "")),
                        evidence_level=str(v.get("evidence_level", "deterministic_check")),
                        pass_condition=str(v.get("pass_condition", "")),
                        estimated_cost=str(v.get("estimated_cost", "")),
                    )
                )

        # Build delivery estimate
        de_data = t.get("delivery_estimate", {})
        delivery = DeliveryEstimate(
            initial_delivery_cost=str(de_data.get("initial_delivery_cost", "")),
            operating_cost=str(de_data.get("operating_cost", "")),
            maintenance_burden=str(de_data.get("maintenance_burden", "")),
        )

        proposals.append(
            ProductThesisProposal(
                problem_model_revision_id=problem.revision_id,
                outcome_contract_revision_id=contract.revision_id,
                name=str(t["name"]),
                product_promise=str(t["product_promise"]),
                differentiation=str(t.get("differentiation", "")),
                realization_modes=t.get("realization_modes", ["software"]),
                mechanism_hypotheses=mechanisms,
                falsifiable_predictions=predictions,
                validation_strategy=validation,
                key_unknowns=t.get("key_unknowns", []),
                key_risks=t.get("key_risks", []),
                delivery_estimate=delivery,
            )
        )

    return tuple(proposals)


def build_theses_prompt(problem: ProblemModel, contract: OutcomeContract) -> str:
    """Build prompt for ProductThesis generation."""
    return f"""Confirmed ProblemModel:
{json.dumps({
    "facts": [{"fact_id": f.fact_id, "statement": f.statement} for f in problem.facts],
    "competing_explanations": [{"explanation_id": e.explanation_id, "statement": e.statement} for e in problem.competing_explanations],
}, ensure_ascii=False, indent=2)}

Confirmed OutcomeContract:
{json.dumps({
    "target_segments": contract.target_segments,
    "target_outcomes": [{"outcome_id": o.outcome_id, "description": o.description} for o in contract.target_outcomes],
    "success_indicators": [{"indicator_id": i.indicator_id, "operational_definition": i.operational_definition} for i in contract.success_indicators],
}, ensure_ascii=False, indent=2)}

Generate 3 distinct ProductThesis candidates, each with meaningfully different mechanisms and approaches."""
