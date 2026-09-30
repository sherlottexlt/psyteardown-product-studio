import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OutcomeContract, ProblemModel } from "../api/types";
import { OutcomeContractEditor, ProblemModelEditor } from "./ContractProposalEditors";

const contract = {
  outcome_contract_id: "contract-1",
  revision_id: "contract-1.r1",
  project_id: "project-1",
  intent_revision_id: "intent-1.r2",
  problem_model_revision_id: "problem-1.r2",
  meta: { revision: 1, parent_revision_id: null, created_at: "2026-09-20T00:00:00Z", created_by: "provider", reason: "proposal" },
  status: "proposed",
  target_segments: ["independent workers"],
  applicable_contexts: ["desktop work"],
  target_outcomes: [{ outcome_id: "outcome-1", description: "fewer interruptions", indicator_ids: ["indicator-1"] }],
  success_indicators: [{ indicator_id: "indicator-1", operational_definition: "unplanned switches", observation_method: "task observation", desired_direction: "decrease", threshold_or_target: "human must set", required_evidence: "real_user_observation" }],
  prohibited_outcomes: [], prohibited_outcomes_reviewed: false,
  resource_boundary: { time_budget: null, economic_budget: null, user_attention_budget: null, maintenance_budget: null, data_boundary: null, explicit_unknowns: ["limits unknown"] },
  stop_conditions: [{ condition_id: "stop-1", condition: "pressure increases", action: "reframe" }],
  minimum_delivery_maturity: "concept", required_real_world_evidence: ["one real task"],
  dependencies: [], confirmation: null, content_hash: "hash",
} satisfies OutcomeContract;

afterEach(() => cleanup());

describe("OutcomeContractEditor", () => {
  it("keeps prohibited-outcome review as an explicit human field", async () => {
    const onSave = vi.fn().mockResolvedValue({ status: "saved" });
    const user = userEvent.setup();
    render(<OutcomeContractEditor contract={contract} busy={false} onCancel={() => undefined} onSave={onSave} />);

    const review = screen.getByLabelText(/我已审查禁止结果与伤害边界/);
    expect(review).not.toBeChecked();
    await user.click(review);
    await user.click(screen.getByRole("button", { name: "保存结果契约提案" }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ prohibitedOutcomesReviewed: true }));
  });
});

const problem = {
  problem_model_id: "problem-1",
  revision_id: "problem-1.r1",
  project_id: "project-1",
  intent_revision_id: "intent-1.r2",
  meta: { revision: 1, parent_revision_id: null, created_at: "2026-09-20T00:00:00Z", created_by: "provider", reason: "proposal" },
  status: "proposed",
  facts: [{ fact_id: "fact-1", statement: "I get stuck comparing options", source_refs: [] }],
  assumptions: [],
  unknowns: [{ unknown_id: "unknown-1", question: "What makes the comparison difficult?", decision_impact: "Could change the product direction", next_step: "Recall one recent example" }],
  competing_explanations: [
    { explanation_id: "explanation-1", statement: "Too much information", supporting_fact_ids: ["fact-1"], contradicting_fact_ids: [], cheapest_falsification: "Compare a shorter list" },
    { explanation_id: "explanation-2", statement: "Options are hard to compare", supporting_fact_ids: ["fact-1"], contradicting_fact_ids: [], cheapest_falsification: "Put attributes side by side" },
  ],
  stakeholder_tensions: [],
  dependencies: [],
  confirmation: null,
  content_hash: "hash",
} as ProblemModel;

describe("ProblemModelEditor", () => {
  it("explains that unknowns are optional questions and how to resolve them", () => {
    render(<ProblemModelEditor problem={problem} busy={false} onCancel={() => undefined} onSave={vi.fn()} />);
    expect(screen.getByText(/暂时不知道：保留问题即可，不要猜/)).toBeInTheDocument();
    expect(screen.getByText(/不需要清空“仍未知”才能确认问题模型或生成结果契约/)).toBeInTheDocument();
    expect(screen.getByText(/只写你亲自知道\/观察到的答案/)).toBeInTheDocument();
  });
});
