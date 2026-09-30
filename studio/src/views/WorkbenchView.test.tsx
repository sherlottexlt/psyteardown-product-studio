import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ProductDeliveryBundle,
  ProductExecutionJob,
  ProductGenerationJob,
  ProductProjectView,
} from "../api/types";
import { WorkbenchView } from "./WorkbenchView";

const view = {
  project: { project_id: "project-1" },
  product_intent: null,
  problem_model: null,
  outcome_contract: null,
  product_theses: [{ thesis_id: "thesis-1", status: "selected", name: "Focus guard", product_promise: "promise", realization_modes: [], differentiation: "d", key_unknowns: ["u"], falsifiable_predictions: [], validation_strategy: [], delivery_estimate: { maintenance_burden: "low" } }],
  web_generation_contract: { status: "confirmed", app_title: "Focus guard", template_id: "react_typescript_vite_spa", template_version: "b2-v1", screens: [], tasks: [] },
  recorded_impacts: [],
} as unknown as ProductProjectView;

const generationJob = { status: "succeeded", consumed_files: 10, consumed_bytes: 100, sandbox: { network_policy: "none", execution_policy: "not_executed" }, budget: { max_bytes: 1000 } } as unknown as ProductGenerationJob;
const executionJob = { job_id: "execution-job-1", revision_id: "execution-job-1.r7", status: "succeeded", checkpoint_step: "browser" } as unknown as ProductExecutionJob;
const bundle = {
  bundle_id: "delivery-bundle-1",
  execution_job_revision_id: "execution-job-1.r7",
  web_generation_contract_revision_id: "web-contract-1.r1",
  materialization_kind: "template",
  archive_sha256: "a".repeat(64),
  archive_bytes: 4096,
  files: [{}, {}],
  outcome_evidence_level: "none",
  unverified_claims: ["No real-user evidence."],
} as unknown as ProductDeliveryBundle;

function renderWorkbench(props: Partial<Parameters<typeof WorkbenchView>[0]> = {}) {
  const onExportProduct = vi.fn();
  render(
    <WorkbenchView
      view={view}
      busy={false}
      onGenerate={vi.fn()}
      onGenerateWeb={vi.fn()}
      onConfirmWeb={vi.fn()}
      generationJob={generationJob}
      executionJob={executionJob}
      onGenerateProduct={vi.fn()}
      onExecuteProduct={vi.fn()}
      onRepairProduct={vi.fn()}
      onExportProduct={onExportProduct}
      deliveryArchiveUrl={(id) => `/archive/${id}`}
      {...props}
    />,
  );
  return onExportProduct;
}

describe("WorkbenchView delivery export", () => {
  afterEach(cleanup);

  it("offers an explicit regeneration action when a Web contract already exists", async () => {
    const onGenerateWeb = vi.fn();
    renderWorkbench({ onGenerateWeb });
    await userEvent.click(screen.getByRole("button", { name: "重新生成 Web 契约提案" }));
    expect(onGenerateWeb).toHaveBeenCalledOnce();
  });

  it("shows the proposed page details before a workspace exists", () => {
    renderWorkbench({
      view: {
        ...view,
        web_generation_contract: {
          ...view.web_generation_contract,
          status: "proposed",
          meta: { revision: 7 },
          primary_flow_task_ids: ["task-frame"],
          screens: [
            { screen_id: "screen-setup", title: "设定这次决定", purpose: "先写清楚决定", task_ids: ["task-frame"], state_ids: [] },
            { screen_id: "screen-compare", title: "选项对比", purpose: "分别记录两个选项", task_ids: ["task-compare"], state_ids: [] },
            { screen_id: "screen-brief", title: "决策简报", purpose: "导出并重新打开", task_ids: ["task-save"], state_ids: [] },
          ],
          tasks: [
            { task_id: "task-frame", goal: "写下决定", success_criteria: "决定清楚", screen_id: "screen-setup" },
            { task_id: "task-compare", goal: "比较选项", success_criteria: "差异可见", screen_id: "screen-compare" },
            { task_id: "task-save", goal: "导出简报", success_criteria: "文件可重开", screen_id: "screen-brief" },
          ],
        },
      } as unknown as ProductProjectView,
    });
    expect(screen.getByText("这就是 r7 会生成的页面")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "设定这次决定" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "选项对比" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "决策简报" })).toBeInTheDocument();
    expect(screen.getByText("导出简报")).toBeInTheDocument();
  });

  it("offers export only after a succeeded execution", async () => {
    const onExport = renderWorkbench();
    await userEvent.click(screen.getByRole("button", { name: "导出交付包" }));
    expect(onExport).toHaveBeenCalledOnce();
    expect(screen.queryByRole("link", { name: /下载交付包/ })).toBeNull();
  });

  it("hides export for an unverified execution", () => {
    renderWorkbench({ executionJob: { ...executionJob, status: "failed" } as ProductExecutionJob });
    expect(screen.queryByRole("button", { name: "导出交付包" })).toBeNull();
  });

  it("explains a contract test harness crash without calling it an app-source failure", () => {
    renderWorkbench({
      executionJob: {
        ...executionJob,
        status: "failed",
        checkpoint_step: "browser",
        error_code: "browser_test_harness_failed",
      } as ProductExecutionJob,
    });
    expect(screen.getByRole("alert")).toHaveTextContent("平台生成的契约浏览器测试脚本自身异常");
    expect(screen.getByRole("button", { name: "定位并尝试受限修复" })).toBeInTheDocument();
  });

  it("stops offering repeated deterministic repair for an unsupported failure", () => {
    renderWorkbench({
      executionJob: { ...executionJob, status: "failed", error_code: "browser_test_harness_failed" } as ProductExecutionJob,
      repairJob: {
        job_id: "repair-1",
        execution_job_id: "execution-job-1",
        status: "failed",
        budget: { max_cost_units: 2 },
        attempts: [{ status: "unsupported", error_code: "unsupported_failure", diagnosis: "No deterministic allowlisted repair is known for this failure.", cost_units: 1, patches: [] }],
      } as never,
    });
    expect(screen.queryByRole("button", { name: "定位并尝试受限修复" })).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("原 workspace 源码未被修改");
    expect(screen.getByRole("status")).toHaveTextContent("不会再重复消耗修复尝试");
  });

  it("shows the matching bundle with download link and unverified claims", () => {
    renderWorkbench({ deliveryBundle: bundle });
    expect(screen.getByRole("link", { name: /下载交付包/ })).toHaveAttribute("href", "/archive/delivery-bundle-1");
    expect(screen.getByText(/静态 HTTP 服务运行/)).toBeInTheDocument();
    expect(screen.getByText("No real-user evidence.")).toBeInTheDocument();
  });

  it("opens the delivered build preview only for the current bundle", () => {
    const preview = { url: (id: string) => `/preview/${id}/`, policy: null, feedback: [], onSubmit: vi.fn(), onWithdraw: vi.fn() };
    renderWorkbench({ deliveryBundle: bundle, preview });
    expect(screen.getByTitle("交付构建预览")).toHaveAttribute("src", "/preview/delivery-bundle-1/");
    cleanup();
    renderWorkbench({ deliveryBundle: { ...bundle, execution_job_revision_id: "execution-job-0.r7" }, preview });
    expect(screen.queryByTitle("交付构建预览")).toBeNull();
    expect(screen.getByText("还没有可预览的交付构建")).toBeInTheDocument();
  });

  it("does not present a bundle from an older execution as current", () => {
    renderWorkbench({ deliveryBundle: { ...bundle, execution_job_revision_id: "execution-job-0.r7" } });
    expect(screen.queryByRole("link", { name: /下载交付包/ })).toBeNull();
    expect(screen.getByRole("button", { name: "导出交付包" })).toBeInTheDocument();
  });

  it("explains what the source model receives and offers a gated retry", async () => {
    const policy = { available: true, provider: "deepseek", model: "deepseek-v4-flash", sent: [], not_sent: [], retention: "local", max_calls_per_job: 2, model_writes: ["src/App.tsx", "src/styles.css"], repair_uses_model: false };
    const failed = {
      ...generationJob,
      status: "failed",
      materialization_kind: "model",
      attempt: 1,
      budget: { max_attempts: 2, max_bytes: 1000 },
      model_calls: [{ attempt: 1, provider: "deepseek", model: "deepseek-flash", outcome: "rejected", input_tokens: 10, output_tokens: 20, duration_seconds: 3, rejection_reasons: ["import of 'axios' is not allowed"] }],
    } as unknown as ProductGenerationJob;
    const sourceModel = { policy, onGenerate: vi.fn(), onRetry: vi.fn() };
    renderWorkbench({ generationJob: failed, executionJob: null, sourceModel });

    expect(screen.getByText(/模型只收到已确认的 Web 契约/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /用模型写源码 · deepseek/ }));
    expect(sourceModel.onGenerate).toHaveBeenCalledOnce();
    expect(screen.getByText("import of 'axios' is not allowed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /带上门禁原因重试/ }));
    expect(sourceModel.onRetry).toHaveBeenCalledOnce();
  });

  it("offers local revalidation of a saved rejected source draft without another provider call", async () => {
    const failed = {
      ...generationJob,
      job_id: "generation-job-rejected",
      status: "failed",
      materialization_kind: "model",
      attempt: 2,
      budget: { max_attempts: 2, max_bytes: 1000 },
      model_calls: [
        { attempt: 1, provider: "deepseek", model: "deepseek-flash", outcome: "failed", duration_seconds: 1, rejection_reasons: [] },
        { attempt: 2, provider: "deepseek", model: "deepseek-flash", outcome: "rejected", duration_seconds: 1, rejection_reasons: ["screen id was not found by an older gate"] },
      ],
    } as unknown as ProductGenerationJob;
    const onRevalidateSavedDraft = vi.fn();
    renderWorkbench({
      generationJob: failed,
      executionJob: null,
      sourceModel: {
        policy: { available: true, provider: "deepseek", model: "deepseek-flash", sent: [], not_sent: [], retention: "local", max_calls_per_job: 2, model_writes: ["src/App.tsx", "src/styles.css"], repair_uses_model: false },
        onGenerate: vi.fn(),
        onRetry: vi.fn(),
        onRevalidateSavedDraft,
      },
    });

    expect(screen.queryByRole("button", { name: /带上门禁原因重试/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "用已保存草稿重新校验（不调用模型）" }));
    expect(onRevalidateSavedDraft).toHaveBeenCalledOnce();
    expect(screen.getByText(/不会再次调用模型/)).toBeInTheDocument();
  });

  it("offers a fresh saved-source workspace lineage without another provider call", async () => {
    const source = {
      ...generationJob,
      job_id: "generation-job-source",
      revision_id: "generation-job-source.r14",
      status: "succeeded",
      materialization_kind: "model",
      attempt: 2,
      consumed_cost_units: 2,
      budget: { max_attempts: 2, max_bytes: 1000 },
      model_calls: [{
        attempt: 2,
        provider: "deepseek",
        model: "deepseek-flash",
        outcome: "rejected",
        static_gate_revalidated: true,
        static_gate_version: "b7m-static-gate-v3",
        duration_seconds: 1,
        rejection_reasons: ["an older local gate did not understand prefixed template IDs"],
      }],
    } as unknown as ProductGenerationJob;
    const onMaterializeSavedSource = vi.fn();
    renderWorkbench({
      generationJob: source,
      executionJob: null,
      sourceModel: {
        policy: { available: true, provider: "deepseek", model: "deepseek-flash", sent: [], not_sent: [], retention: "local", max_calls_per_job: 2, model_writes: ["src/App.tsx", "src/styles.css"], repair_uses_model: false },
        onGenerate: vi.fn(),
        onRetry: vi.fn(),
        onMaterializeSavedSource,
      },
    });

    expect(screen.getByText("本地复核通过（provider 原始结果保留）")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "从已验证源码创建新 workspace（不调用模型）" }));
    expect(onMaterializeSavedSource).toHaveBeenCalledOnce();
    expect(screen.getByText(/旧 job、workspace 和执行记录保持不变，不调用模型/)).toBeInTheDocument();
  });

  it("disables model generation when no source model is configured", () => {
    renderWorkbench({ sourceModel: { policy: { available: false } as never, onGenerate: vi.fn(), onRetry: vi.fn() } });
    expect(screen.getByRole("button", { name: "模型写源码（未配置）" })).toBeDisabled();
    expect(screen.getByText(/PSYTEARDOWN_PRODUCT_SOURCE_MODEL=deepseek/)).toBeInTheDocument();
  });

  it("shows the delivery diff honestly, including when source and build are unchanged", async () => {
    const onDisposition = vi.fn();
    const feedback = {
      feedback_id: "preview-feedback-1",
      delivery_bundle_id: "delivery-bundle-1",
      status: "submitted",
      disposition: "pending",
      text: "Stop is unclear",
      meta: { revision: 1 },
    };
    renderWorkbench({
      view: {
        ...view,
        web_generation_contract: {
          ...view.web_generation_contract,
          source_refs: [{ source_type: "preview_feedback", source_id: "preview-feedback-1" }],
          meta: { revision: 3 },
        },
      } as unknown as ProductProjectView,
      preview: {
        url: (id) => `/preview/${id}/`,
        policy: null,
        feedback: [feedback] as never,
        onSubmit: vi.fn(),
        onWithdraw: vi.fn(),
        onDisposition,
        diff: {
          base_bundle_id: "delivery-bundle-1",
          target_bundle_id: "delivery-bundle-2",
          base_contract_revision_id: "web-contract-1.r2",
          target_contract_revision_id: "web-contract-1.r4",
          contract_changes: ["acceptance_checks: added job-feedback-check"],
          files: [
            { path: "DELIVERY.md", change: "modified", base_sha256: "a", target_sha256: "b" },
            { path: "source/src/App.tsx", change: "unchanged", base_sha256: "c", target_sha256: "c" },
          ],
        },
      },
    });

    const diff = screen.getByRole("region", { name: "交付版本差异" });
    expect(diff).toHaveTextContent("源码与构建未变化");
    expect(diff).toHaveTextContent("acceptance_checks: added job-feedback-check");
    expect(diff).toHaveTextContent("DELIVERY.md");
    expect(diff).not.toHaveTextContent("source/src/App.tsx");
    await userEvent.click(screen.getByRole("button", { name: "标记已采纳" }));
    expect(onDisposition).toHaveBeenCalledWith(feedback, "incorporated");
  });
});
