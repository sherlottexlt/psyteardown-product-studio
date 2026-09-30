import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  endC1Envelope,
  getC1Policy,
  listC1Envelopes,
  listC1Observations,
  listC1Participants,
  listC1Reviews,
  presentC1Task,
  recordC1Observation,
  reviewC1Evidence,
} from "../api/client";
import { C1Panel } from "./C1Panel";

vi.mock("../api/client", () => ({
  endC1Envelope: vi.fn(),
  enrollC1Participant: vi.fn(),
  getC1Policy: vi.fn(),
  listC1Envelopes: vi.fn(),
  listC1Observations: vi.fn(),
  listC1Participants: vi.fn(),
  listC1Reviews: vi.fn(),
  presentC1Task: vi.fn(),
  recordC1Observation: vi.fn(),
  reviewC1Evidence: vi.fn(),
  startC1Envelope: vi.fn(),
  withdrawC1Participant: vi.fn(),
}));

const policy = {
  trial_state: "available",
  trial_status_message: "本地 C1 试用可启动。",
  consent_policy_revision: "c1-local-v1",
  statement: "Only a random participant ID and structured task results are recorded.",
  access_policy: ["local_host", "named_reviewer"],
  data_categories: ["random_participant_id", "structured_task_measure_value"],
  retention_policy: "At most 30 days after envelope close.",
  withdrawal_policy: "Withdrawal erases source records.",
  source_layer: "research_observation",
  evidence_ceiling: "observed",
};

const envelope = {
  envelope_id: "envelope-1",
  revision_id: "envelope-1.r1",
  project_id: "project-1",
  status: "active",
  measurement_plan_revision_id: "plan-1.r2",
  delivery_bundle_id: "bundle-1",
  delivery_bundle_revision_id: "bundle-1.r1",
  execution_job_revision_id: "execution-1.r1",
  web_generation_contract_revision_id: "web-contract-1.r1",
  host: "local-host",
  consent_policy_revision: "c1-local-v1",
  consent_statement: policy.statement,
  access_policy: policy.access_policy,
  data_categories: policy.data_categories,
  retention_policy: policy.retention_policy,
  withdrawal_policy: policy.withdrawal_policy,
  meta: { revision: 1, parent_revision_id: null, created_at: "2026-09-26T00:00:00Z", created_by: "local-host", reason: "test" },
};

const participant = {
  participant_id: "participant-1",
  revision_id: "participant-1.r1",
  project_id: "project-1",
  envelope_id: "envelope-1",
  consent_receipt_id: "consent-1",
  consent_receipt_revision_id: "consent-1.r1",
  status: "active",
  enrolled_at: "2026-09-26T00:00:00Z",
  withdrawn_at: null,
  meta: { revision: 1, parent_revision_id: null, created_at: "2026-09-26T00:00:00Z", created_by: "local-host", reason: "test" },
};

const observation = (id: string, measureId: string, value: string | number | null, status = "observed") => ({
  observation_id: id,
  revision_id: `${id}.r1`,
  project_id: "project-1",
  envelope_id: "envelope-1",
  participant_id: "participant-1",
  presentation_id: "presentation-1",
  measurement_plan_revision_id: "plan-1.r2",
  measure_id: measureId,
  source_layer: "research_observation",
  value,
  status,
  completion_cause: status === "observed" ? null : "participant stopped",
  consent_receipt_revision_id: "consent-1.r1",
  delivery_bundle_id: "bundle-1",
  delivery_bundle_revision_id: "bundle-1.r1",
  execution_job_revision_id: "execution-1.r1",
  web_generation_contract_revision_id: "web-contract-1.r1",
  recorded_by: "local-host",
  recorded_at: "2026-09-26T00:01:00Z",
  evidence_refs: [],
  meta: { revision: 1, parent_revision_id: null, created_at: "2026-09-26T00:01:00Z", created_by: "local-host", reason: "test" },
});

function makePlan() {
  return {
    measurement_plan_id: "plan-1",
    revision_id: "plan-1.r2",
    project_id: "project-1",
    outcome_contract_revision_id: "outcome-1.r1",
    meta: { revision: 2, parent_revision_id: "plan-1.r1", created_at: "2026-09-26T00:00:00Z", created_by: "test", reason: "test" },
    status: "confirmed",
    plan_version: "c2-v1",
    origin: "deterministic_derivation",
    measures: [
      { measure_id: "measure-1", label: "Observed switches", source_layer: "research_observation", value_kind: "count", primary: true },
      { measure_id: "measure-2", label: "Observed duration", source_layer: "research_observation", value_kind: "duration_seconds", primary: false },
    ],
    guardrails: [], stop_condition_ids: [], sample_plan: {}, observation_window: "one session", consent_scope: "explicit", withdrawal_policy: "withdraw any time", dependencies: [], confirmation: {}, blockers: [], content_hash: "hash",
  };
}

const view = {
  project: { project_id: "project-1" },
  web_generation_contract: { tasks: [{ task_id: "task-1" }] },
} as any;

function renderPanel(overrides: Partial<React.ComponentProps<typeof C1Panel>> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <C1Panel
        projectId="project-1"
        view={view}
        plan={makePlan() as any}
        deliveryBundle={{ bundle_id: "bundle-1", execution_job_revision_id: "execution-1.r1", web_generation_contract_revision_id: "web-contract-1.r1", contract_is_current: true } as any}
        executionJob={{ status: "succeeded" } as any}
        onChanged={vi.fn().mockResolvedValue(undefined)}
        onError={vi.fn()}
        {...overrides}
      />
    </QueryClientProvider>,
  );
}

describe("C1Panel", () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("keeps envelope creation disabled until a current delivery is available", async () => {
    vi.mocked(getC1Policy).mockResolvedValue(policy as any);
    vi.mocked(listC1Envelopes).mockResolvedValue([]);
    vi.mocked(listC1Participants).mockResolvedValue([]);
    vi.mocked(listC1Observations).mockResolvedValue([]);
    vi.mocked(listC1Reviews).mockResolvedValue([]);

    renderPanel({ deliveryBundle: null, executionJob: null });

    expect(await screen.findByText("先完成上面的产品可用性确认；B4/B6 通过不等于产品已经适合真实任务。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始本地 C1 试用" })).toBeDisabled();
    expect(await screen.findByText(policy.statement)).toBeInTheDocument();
  });


  it("ends an active trial with an explicit reason", async () => {
    vi.mocked(getC1Policy).mockResolvedValue(policy as any);
    vi.mocked(listC1Envelopes).mockResolvedValue([envelope] as any);
    vi.mocked(listC1Participants).mockResolvedValue([]);
    vi.mocked(listC1Observations).mockResolvedValue([]);
    vi.mocked(listC1Reviews).mockResolvedValue([]);
    vi.mocked(endC1Envelope).mockResolvedValue({ ...envelope, status: "closed", closed_at: "2026-09-27T00:00:00Z", retention_expires_at: "2026-10-27T00:00:00Z" } as any);

    const user = userEvent.setup();
    renderPanel();
    await user.type(await screen.findByLabelText("结束原因"), "本次本地试用完成");
    await user.click(screen.getByRole("button", { name: "结束 trial" }));
    await waitFor(() => expect(endC1Envelope).toHaveBeenCalledWith({ projectId: "project-1", envelopeId: "envelope-1", action: "close", reason: "本次本地试用完成" }));
  });

  it("records non-success paths without a value and reviews one observation at a time", async () => {
    const observations = [observation("observation-1", "measure-1", 2), observation("observation-2", "measure-2", 45)];
    let reviews: any[] = [];
    vi.mocked(getC1Policy).mockResolvedValue(policy as any);
    vi.mocked(listC1Envelopes).mockResolvedValue([envelope] as any);
    vi.mocked(listC1Participants).mockResolvedValue([participant] as any);
    vi.mocked(listC1Observations).mockResolvedValue(observations as any);
    vi.mocked(listC1Reviews).mockImplementation(async () => reviews as any);
    vi.mocked(presentC1Task).mockResolvedValue({ presentation_id: "presentation-1" } as any);
    vi.mocked(recordC1Observation).mockResolvedValue(observation("observation-3", "measure-1", null, "technical_failure") as any);
    vi.mocked(reviewC1Evidence).mockImplementation(async (input) => {
      const review = { review_id: "review-1", observation_ids: input.observationIds, decision: input.decision, evidence_level_after: input.evidenceLevelAfter };
      reviews = [review];
      return review as any;
    });

    const user = userEvent.setup();
    renderPanel();

    await screen.findByText("participant-1");
    await user.click(screen.getByRole("button", { name: "开始任务 presentation" }));
    await user.selectOptions(screen.getByLabelText("状态"), "technical_failure");
    await user.type(screen.getByLabelText("非成功原因（可复核）"), "浏览器未能启动");
    await user.click(screen.getByRole("button", { name: "保存观察" }));
    await waitFor(() => expect(recordC1Observation).toHaveBeenCalledWith(expect.objectContaining({ value: null, completionCause: "浏览器未能启动", status: "technical_failure" })));

    const reviewSelect = screen.getByRole("combobox", { name: "待审观察" });
    expect(reviewSelect).toHaveValue("observation-1");
    await user.type(screen.getByLabelText("reviewer（需与 host 分离）"), "reviewer-li");
    await user.click(screen.getByRole("button", { name: "提交人工 review" }));
    await waitFor(() => expect(reviewC1Evidence).toHaveBeenCalledWith(expect.objectContaining({ observationIds: ["observation-1"] })));
  });
});

