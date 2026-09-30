import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ApiClientError,
  confirmWebGenerationContract,
  createGenerationJob,
  createExecutionJob,
  listGenerationJobs,
  listExecutionJobs,
  runGenerationJob,
  retryGenerationJob,
  revalidateSavedModelDraft,
  retryProposalJob,
  getSourceModelPolicy,
  cancelExecutionJob,
  createSavedSourceMaterialization,
  recoverExecutionJob,
  retryExecutionJob,
  pauseGenerationJob,
  resumeGenerationJob,
  cancelGenerationJob,
  runExecutionJob,
  createRepairJob,
  listRepairJobs,
  runRepairJob,
  retryRepairJob,
  createDeliveryBundle,
  listDeliveryBundles,
  deliveryBundleArchiveUrl,
  deliveryBundlePreviewUrl,
  getPreviewFeedbackPolicy,
  listPreviewFeedback,
  submitPreviewFeedback,
  withdrawPreviewFeedback,
  setPreviewFeedbackDisposition,
  diffDeliveryBundles,
  confirmRevision,
  createProposalJob,
  deriveOutcomeMeasurementPlan,
  getProject,
  listProposalJobs,
  reviseOutcomeContract,
  reviseOutcomeMeasurementPlan,
  reviseProblemModel,
  reviseProductIntent,
  runProposalJob,
  transitionThesis,
} from "../api/client";
import type {
  PreviewFeedback,
  PreviewFeedbackDisposition,
  EditableOutcomeContract,
  EditableProblemModel,
  EditableProductIntent,
  ProductProjectView,
  ProductThesis,
  ProposalJobKind,
  RevisionWriteResult,
} from "../api/types";
import { Badge, statusLabel } from "../components/Badge";
import { formatApiError, humanDecisionCount } from "../domain/project";
import { CommandView } from "./CommandView";
import { ContractView } from "./ContractView";
import { DecisionsView } from "./DecisionsView";
import { EvidenceView } from "./EvidenceView";
import { C1Panel } from "./C1Panel";
import { MainlineGuide } from "../components/MainlineGuide";
import { WorkbenchView } from "./WorkbenchView";
import type { PreviewFeedbackDraft } from "./PreviewFeedbackPanel";

type Area = "command" | "contract" | "workbench" | "decisions" | "evidence";

type ProposalProvider = "deterministic_fake" | "real";

const navigation: Array<{ id: Area; label: string; index: string }> = [
  { id: "command", label: "对话与指挥", index: "01" },
  { id: "contract", label: "产品契约", index: "02" },
  { id: "workbench", label: "产品工作台", index: "03" },
  { id: "decisions", label: "决策与待办", index: "04" },
  { id: "evidence", label: "证据与进度", index: "05" },
];

function modeLabel(mode: string): string {
  return { managed: "托管模式", co_design: "共同设计", governance: "治理模式" }[mode] ?? mode;
}

export function ProjectStudio({ projectId, onExit }: { projectId: string; onExit: () => void }) {
  const [area, setArea] = useState<Area>("contract");
  // Keep the local path deterministic; real DeepSeek remains an explicit provider choice.
  const [proposalProvider, setProposalProvider] = useState<ProposalProvider>("deterministic_fake");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resumingPending, setResumingPending] = useState(false);
  const query = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    retry: false,
  });
  const jobsQuery = useQuery({
    queryKey: ["proposal-jobs", projectId],
    queryFn: () => listProposalJobs(projectId),
    retry: false,
  });
  const generationJobsQuery = useQuery({
    queryKey: ["generation-jobs", projectId],
    queryFn: () => listGenerationJobs(projectId),
    retry: false,
  });
  const executionJobsQuery = useQuery({
    queryKey: ["execution-jobs", projectId],
    queryFn: () => listExecutionJobs(projectId),
    retry: false,
  });
  const repairJobsQuery = useQuery({
    queryKey: ["repair-jobs", projectId],
    queryFn: () => listRepairJobs(projectId),
    retry: false,
  });
  const deliveryBundlesQuery = useQuery({
    queryKey: ["delivery-bundles", projectId],
    queryFn: () => listDeliveryBundles(projectId),
    retry: false,
  });

  const sourceModelPolicyQuery = useQuery({
    queryKey: ["source-model-policy"],
    queryFn: getSourceModelPolicy,
    retry: false,
  });
  const feedbackPolicyQuery = useQuery({
    queryKey: ["preview-feedback-policy"],
    queryFn: getPreviewFeedbackPolicy,
    retry: false,
  });
  const previewFeedbackQuery = useQuery({
    queryKey: ["preview-feedback", projectId],
    queryFn: () => listPreviewFeedback(projectId),
    retry: false,
  });
  const generationJobs = generationJobsQuery.data ?? [];
  const currentContractRevisionId = query.data?.web_generation_contract?.revision_id;
  const currentGenerationJobs = currentContractRevisionId
    ? generationJobs.filter((job) => job.web_generation_contract_revision_id === currentContractRevisionId)
    : generationJobs;
  const pendingGenerationJob = [...currentGenerationJobs].reverse().find((job) => ["queued", "running", "paused"].includes(job.status));
  const successfulTemplateJob = [...currentGenerationJobs].reverse().find((job) => job.status === "succeeded" && job.materialization_kind === "template");
  // Prefer a live job, then the latest successful template. Historical model
  // failures must not hide a usable deterministic workspace for this contract.
  const selectedGenerationJob = pendingGenerationJob ?? successfulTemplateJob ?? currentGenerationJobs.at(-1) ?? generationJobs.at(-1) ?? null;
  const latestModelJob = [...currentGenerationJobs].reverse().find((job) => job.materialization_kind === "model") ?? null;
  const latestSavedSourceJob = [...currentGenerationJobs].reverse().find((job) => job.materialization_kind === "model" && job.status === "succeeded" && job.model_calls.at(-1)?.static_gate_revalidated) ?? null;
  const executionJobs = executionJobsQuery.data ?? [];
  const selectedExecutionJob = selectedGenerationJob
    ? [...executionJobs].reverse().find((job) => job.generation_job_id === selectedGenerationJob.job_id) ?? null
    : executionJobs.at(-1) ?? null;
  const repairJobs = repairJobsQuery.data ?? [];
  const selectedRepairJob = selectedExecutionJob
    ? [...repairJobs].reverse().find((job) => job.execution_job_id === selectedExecutionJob.job_id) ?? null
    : repairJobs.at(-1) ?? null;

  const bundles = deliveryBundlesQuery.data ?? [];
  const diffBase = bundles.length >= 2 ? bundles[bundles.length - 2] : null;
  const diffTarget = bundles.length >= 2 ? bundles[bundles.length - 1] : null;
  const bundleDiffQuery = useQuery({
    queryKey: ["delivery-bundle-diff", projectId, diffBase?.bundle_id, diffTarget?.bundle_id],
    queryFn: () => diffDeliveryBundles({ projectId, baseBundleId: diffBase!.bundle_id, targetBundleId: diffTarget!.bundle_id }),
    enabled: Boolean(diffBase && diffTarget),
    retry: false,
  });

  async function refreshAfter(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      await query.refetch();
      await generationJobsQuery.refetch();
      await executionJobsQuery.refetch();
      await repairJobsQuery.refetch();
    } catch (error) {
      setActionError(formatApiError(error));
    } finally {
      setBusy(false);
    }
  }

  async function resumePendingWork() {
    const pendingGeneration = selectedGenerationJob;
    const pendingExecution = selectedExecutionJob;
    const pendingProposal = jobsQuery.data?.at(-1);
    setResumingPending(true);
    setActionError(null);
    try {
      if (pendingProposal && ["queued", "running"].includes(pendingProposal.status)) {
        await runProposalJob({ projectId, jobId: pendingProposal.job_id });
      } else if (pendingGeneration && pendingGeneration.status === "paused") {
        await resumeGenerationJob({ projectId, jobId: pendingGeneration.job_id });
        await runGenerationJob({ projectId, jobId: pendingGeneration.job_id });
      } else if (pendingGeneration && ["queued", "running"].includes(pendingGeneration.status)) {
        await runGenerationJob({ projectId, jobId: pendingGeneration.job_id });
      } else if (pendingExecution && pendingExecution.status === "queued") {
        await runExecutionJob({ projectId, jobId: pendingExecution.job_id });
      } else if (pendingExecution && pendingExecution.status === "running") {
        await recoverExecutionJob({ projectId, jobId: pendingExecution.job_id });
        await runExecutionJob({ projectId, jobId: pendingExecution.job_id });
      }
      await Promise.all([query.refetch(), jobsQuery.refetch(), generationJobsQuery.refetch(), executionJobsQuery.refetch(), deliveryBundlesQuery.refetch()]);
    } catch (error) {
      setActionError(formatApiError(error));
    } finally {
      setResumingPending(false);
    }
  }

  function pendingWorkLabel(): string | null {
    const proposal = jobsQuery.data?.at(-1);
    if (proposal && ["queued", "running"].includes(proposal.status)) return `提案 Job（${proposal.kind}）`;
    const generation = selectedGenerationJob;
    if (generation && ["queued", "running", "paused"].includes(generation.status)) return `产品生成 Job（${generation.status}）`;
    const execution = selectedExecutionJob;
    if (execution && execution.status === "queued") return "本地验证 Job（queued）";
    if (execution && execution.status === "running") return "本地验证 Job（上次中断，需确认恢复）";
    return null;
  }

  function handleConfirm(
    view: ProductProjectView,
    type: "product-intent" | "problem-model" | "outcome-contract" | "outcome-measurement-plan",
  ) {
    const object = {
      "product-intent": view.product_intent,
      "problem-model": view.problem_model,
      "outcome-contract": view.outcome_contract,
      "outcome-measurement-plan": view.outcome_measurement_plan,
    }[type];
    if (!object) return;
    const objectId = "intent_id" in object
      ? object.intent_id
      : "problem_model_id" in object
        ? object.problem_model_id
        : "outcome_contract_id" in object
          ? object.outcome_contract_id
          : object.measurement_plan_id;
    void refreshAfter(() => confirmRevision({
      projectId,
      objectType: type,
      objectId,
      revision: object.meta.revision,
      reason: `Confirmed ${type} in Product Studio`,
    }));
  }

  function handleDeriveMeasurementPlan() {
    const plan = query.data?.outcome_measurement_plan;
    void refreshAfter(() => deriveOutcomeMeasurementPlan({
      projectId,
      measurementPlanId: plan?.measurement_plan_id,
      expectedRevision: plan?.meta.revision,
    }));
  }

  async function handleMeasurementPlanRevision(thresholds: Record<string, string>): Promise<RevisionWriteResult> {
    const plan = query.data?.outcome_measurement_plan;
    if (!plan) return { status: "error", message: "当前测量计划不可用，请刷新后重试。" };
    setBusy(true);
    setActionError(null);
    try {
      await reviseOutcomeMeasurementPlan({ projectId, plan, thresholds });
      await query.refetch();
      return { status: "saved" };
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "revision_conflict") {
        const refreshed = await query.refetch();
        return {
          status: "conflict",
          latestRevision: refreshed.data?.outcome_measurement_plan?.meta.revision ?? plan.meta.revision,
        };
      }
      return { status: "error", message: formatApiError(error) };
    } finally {
      setBusy(false);
    }
  }

  function handleThesisTransition(thesis: ProductThesis, status: "exploring" | "selected") {
    void refreshAfter(() => transitionThesis({
      projectId,
      thesis,
      toStatus: status,
      reason: status === "selected" ? "Selected in Product Studio" : "Authorized low-cost exploration in Product Studio",
    }));
  }

  async function handleIntentRevision(draft: EditableProductIntent): Promise<RevisionWriteResult> {
    const intent = query.data?.product_intent;
    if (!intent) return { status: "error", message: "当前产品意图不可用，请刷新后重试。" };
    setBusy(true);
    setActionError(null);
    try {
      await reviseProductIntent({ projectId, intent, draft });
      await query.refetch();
      return { status: "saved" };
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "revision_conflict") {
        const refreshed = await query.refetch();
        return {
          status: "conflict",
          latestRevision: refreshed.data?.product_intent?.meta.revision ?? intent.meta.revision,
        };
      }
      return { status: "error", message: formatApiError(error) };
    } finally {
      setBusy(false);
    }
  }

  async function handleProblemRevision(draft: EditableProblemModel): Promise<RevisionWriteResult> {
    const problem = query.data?.problem_model;
    if (!problem) return { status: "error", message: "当前问题模型不可用，请刷新后重试。" };
    setBusy(true);
    try {
      await reviseProblemModel({ projectId, problem, draft });
      await query.refetch();
      return { status: "saved" };
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "revision_conflict") {
        const refreshed = await query.refetch();
        return { status: "conflict", latestRevision: refreshed.data?.problem_model?.meta.revision ?? problem.meta.revision };
      }
      return { status: "error", message: formatApiError(error) };
    } finally { setBusy(false); }
  }

  async function handleOutcomeRevision(draft: EditableOutcomeContract): Promise<RevisionWriteResult> {
    const contract = query.data?.outcome_contract;
    if (!contract) return { status: "error", message: "当前结果契约不可用，请刷新后重试。" };
    setBusy(true);
    try {
      await reviseOutcomeContract({ projectId, contract, draft });
      await query.refetch();
      return { status: "saved" };
    } catch (error) {
      if (error instanceof ApiClientError && error.code === "revision_conflict") {
        const refreshed = await query.refetch();
        return { status: "conflict", latestRevision: refreshed.data?.outcome_contract?.meta.revision ?? contract.meta.revision };
      }
      return { status: "error", message: formatApiError(error) };
    } finally { setBusy(false); }
  }

  async function handleRetryProposal() {
    const job = jobsQuery.data?.at(-1);
    if (!job || !["failed", "stale_input"].includes(job.status)) return;
    setBusy(true);
    setActionError(null);
    try {
      const queued = await retryProposalJob({ projectId, jobId: job.job_id });
      await jobsQuery.refetch();
      const completed = await runProposalJob({ projectId, jobId: queued.job_id });
      await Promise.all([query.refetch(), jobsQuery.refetch()]);
      if (completed.status !== "succeeded") setActionError(completed.error_summary ?? "提案重试没有成功完成。");
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleGenerate(kind: ProposalJobKind) {
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createProposalJob({ projectId, kind, provider: kind === "web_generation_contract" ? "deterministic_fake" : proposalProvider });
      await jobsQuery.refetch();
      const completed = await runProposalJob({ projectId, jobId: queued.job_id });
      await Promise.all([query.refetch(), jobsQuery.refetch()]);
      if (completed.status !== "succeeded") {
        setActionError(
          completed.status === "stale_input"
            ? "生成输入已经变化，结果未提交。请确认最新上游内容后重新发起。"
            : completed.error_summary ?? "提案任务没有成功完成。",
        );
      }
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleGenerateProduct(source: "template" | "model" = "template") {
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createGenerationJob({ projectId, source });
      await generationJobsQuery.refetch();
      const completed = await runGenerationJob({ projectId, jobId: queued.job_id });
      await generationJobsQuery.refetch();
      if (completed.status !== "succeeded") {
        setActionError(completed.error_summary ?? "生成 workspace 未完成。");
      }
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleRevalidateSavedModelDraft() {
    const job = latestModelJob;
    if (!job || job.materialization_kind !== "model" || !["failed", "succeeded"].includes(job.status)) return;
    setBusy(true);
    setActionError(null);
    try {
      const completed = await revalidateSavedModelDraft({ projectId, jobId: job.job_id });
      await generationJobsQuery.refetch();
      if (completed.status !== "succeeded") {
        setActionError(completed.error_summary ?? "本地草稿校验未通过；没有再次调用模型。");
      }
    } catch (error) {
      setActionError(formatApiError(error));
      await generationJobsQuery.refetch();
    } finally {
      setBusy(false);
    }
  }

  async function handleMaterializeSavedSource(sourceJobId?: string) {
    const sourceJob = sourceJobId
      ? generationJobsQuery.data?.find((job) => job.job_id === sourceJobId)
      : [...(generationJobsQuery.data ?? [])].reverse().find((job) =>
          job.materialization_kind === "model" &&
          job.status === "succeeded" &&
          job.model_calls.at(-1)?.static_gate_revalidated,
        );
    if (!sourceJob || sourceJob.materialization_kind !== "model" || sourceJob.status !== "succeeded" || !sourceJob.model_calls.at(-1)?.static_gate_revalidated) return;
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createSavedSourceMaterialization({ projectId, sourceJobId: sourceJob.job_id });
      await generationJobsQuery.refetch();
      const completed = queued.status === "queued"
        ? await runGenerationJob({ projectId, jobId: queued.job_id })
        : queued;
      await generationJobsQuery.refetch();
      if (completed.status !== "succeeded") {
        setActionError(completed.error_summary ?? "新 workspace lineage 未完成；原源码及旧 workspace 均保留。没有调用模型。");
      }
    } catch (error) {
      setActionError(formatApiError(error));
      await generationJobsQuery.refetch();
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryModelSource() {
    const job = latestModelJob;
    if (!job || job.materialization_kind !== "model") return;
    setBusy(true);
    setActionError(null);
    try {
      await retryGenerationJob({ projectId, jobId: job.job_id });
      const completed = await runGenerationJob({ projectId, jobId: job.job_id });
      await generationJobsQuery.refetch();
      if (completed.status !== "succeeded") {
        setActionError(completed.error_summary ?? "模型源码未通过。");
      }
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleExecuteProduct() {
    const generationJob = selectedGenerationJob;
    if (!generationJob || generationJob.status !== "succeeded") {
      setActionError("请先完成成功的 Web workspace 生成。");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createExecutionJob({ projectId, generationJobId: generationJob.job_id });
      await executionJobsQuery.refetch();
      const completed = await runExecutionJob({ projectId, jobId: queued.job_id });
      await executionJobsQuery.refetch();
      if (completed.status !== "succeeded") setActionError(completed.error_summary ?? "执行 sandbox 未完成。");
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleRepairProduct() {
    const executionJob = selectedExecutionJob;
    if (!executionJob || !["failed", "budget_exhausted"].includes(executionJob.status)) {
      setActionError("请先完成一个失败的 B4 执行 Job。");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createRepairJob({ projectId, executionJobId: executionJob.job_id });
      await repairJobsQuery.refetch();
      const ready = ["failed", "stale_input"].includes(queued.status)
        ? await retryRepairJob({ projectId, jobId: queued.job_id })
        : queued;
      const completed = ready.status === "queued"
        ? await runRepairJob({ projectId, jobId: ready.job_id })
        : ready;
      await Promise.all([repairJobsQuery.refetch(), generationJobsQuery.refetch(), executionJobsQuery.refetch()]);
      if (completed.status !== "succeeded") setActionError(completed.error_summary ?? "受限修复未完成。");
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleExportProduct() {
    const executionJob = selectedExecutionJob;
    if (!executionJob || executionJob.status !== "succeeded") {
      setActionError("只有成功完成 B4 验证的执行才能导出交付包。");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await createDeliveryBundle({ projectId, executionJobId: executionJob.job_id });
      await deliveryBundlesQuery.refetch();
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  async function handleSubmitFeedback(bundleId: string, draft: PreviewFeedbackDraft): Promise<boolean> {
    const policy = feedbackPolicyQuery.data;
    if (!policy) {
      setActionError("反馈政策尚未加载，无法记录同意。");
      return false;
    }
    setBusy(true);
    setActionError(null);
    try {
      await submitPreviewFeedback({ projectId, bundleId, ...draft, consentVersion: policy.consent_version });
      await previewFeedbackQuery.refetch();
      return true;
    } catch (error) {
      setActionError(formatApiError(error));
      return false;
    } finally { setBusy(false); }
  }

  function handleWithdrawFeedback(item: PreviewFeedback) {
    void refreshAfter(async () => {
      await withdrawPreviewFeedback({ projectId, feedbackId: item.feedback_id, expectedRevision: item.meta.revision });
      await previewFeedbackQuery.refetch();
    });
  }

  async function handleIterateFromFeedback(item: PreviewFeedback) {
    setBusy(true);
    setActionError(null);
    try {
      const queued = await createProposalJob({ projectId, kind: "web_generation_contract", feedbackId: item.feedback_id });
      const completed = await runProposalJob({ projectId, jobId: queued.job_id });
      await Promise.all([query.refetch(), jobsQuery.refetch()]);
      if (completed.status !== "succeeded") {
        setActionError(
          completed.status === "stale_input"
            ? "反馈已撤回或契约已变化，新的契约提案没有提交。"
            : completed.error_summary ?? "迭代提案没有成功完成。",
        );
      }
    } catch (error) {
      setActionError(formatApiError(error));
    } finally { setBusy(false); }
  }

  function handleFeedbackDisposition(item: PreviewFeedback, disposition: PreviewFeedbackDisposition) {
    void refreshAfter(async () => {
      await setPreviewFeedbackDisposition({ projectId, feedbackId: item.feedback_id, disposition, expectedRevision: item.meta.revision });
      await previewFeedbackQuery.refetch();
    });
  }

  if (query.isLoading) {
    return <main className="loading-screen"><div className="loading-mark"><span /><span /><span /></div><p>正在读取产品模型…</p></main>;
  }
  if (query.isError || !query.data) {
    return <main className="error-screen"><p className="eyebrow">Workspace unavailable</p><h1>无法打开这个产品工作空间</h1><p>{formatApiError(query.error)}</p><div><button className="button button--primary" onClick={() => void query.refetch()}>重试</button><button className="button button--quiet" onClick={onExit}>返回新建项目</button></div></main>;
  }

  const view = query.data;
  const decisions = humanDecisionCount(view);
  return (
    <main className="studio-shell">
      <aside className="studio-sidebar">
        <button className="brand brand--button" onClick={onExit} aria-label="返回 Product Studio 首页">
          <span className="brand__signal" aria-hidden="true"><i /><i /><i /></span><span>psyteardown</span>
        </button>
        <div className="project-switcher"><span>当前计划</span><strong>{view.project.name}</strong><small>{modeLabel(view.project.collaboration_mode)} · r{view.project.meta.revision}</small></div>
        <nav aria-label="产品工作区">
          {navigation.map((item) => (
            <button className={area === item.id ? "is-active" : ""} key={item.id} onClick={() => setArea(item.id)}>
              <span>{item.index}</span>{item.label}
              {item.id === "decisions" && decisions ? <i>{decisions}</i> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="status-light" /><div><strong>本地工作空间</strong><small>数据保存在本机 SQLite</small></div></div>
      </aside>
      <section className="studio-main">
        <header className="studio-topbar">
          <div><span className="mobile-brand">psyteardown</span><Badge tone={view.project.status === "active" ? "good" : "warn"}>{statusLabel(view.project.status)}</Badge><span className="topbar-id">{view.project.project_id}</span></div>
          <div><button className="icon-button" onClick={() => void query.refetch()} title="刷新" aria-label="刷新项目">↻</button><span className="topbar-separator" /><span className="save-status">所有结构化更改由后端保存</span></div>
        </header>
        <nav className="mobile-nav" aria-label="移动端产品工作区">{navigation.map((item) => <button className={area === item.id ? "is-active" : ""} onClick={() => setArea(item.id)} key={item.id}>{item.label}</button>)}</nav>
        <MainlineGuide
          view={view}
          generationJob={selectedGenerationJob}
          executionJob={selectedExecutionJob}
          deliveryBundle={deliveryBundlesQuery.data?.at(-1) ?? null}
          onNavigate={setArea}
          pendingWorkLabel={pendingWorkLabel()}
          onResumePending={() => void resumePendingWork()}
          pendingWorkBusy={resumingPending}
        />
        {actionError ? <div className="action-error" role="alert"><span>{actionError}</span><button onClick={() => setActionError(null)}>关闭</button></div> : null}
        <div className="studio-content">
          {area === "command" ? <CommandView view={view} /> : null}
          {area === "contract" ? <ContractView view={view} busy={busy} latestJob={jobsQuery.data?.at(-1) ?? null} proposalProvider={proposalProvider} onProposalProviderChange={setProposalProvider} onGenerate={handleGenerate} onRetryLatest={() => void handleRetryProposal()} onReviseIntent={handleIntentRevision} onReviseProblem={handleProblemRevision} onReviseOutcome={handleOutcomeRevision} /> : null}
          {area === "workbench" ? <WorkbenchView view={view} busy={busy} generationJob={selectedGenerationJob} executionJob={selectedExecutionJob} repairJob={selectedRepairJob} deliveryBundle={deliveryBundlesQuery.data?.at(-1) ?? null} deliveryArchiveUrl={(bundleId) => deliveryBundleArchiveUrl(projectId, bundleId)} preview={{
            url: (bundleId) => deliveryBundlePreviewUrl(projectId, bundleId),
            policy: feedbackPolicyQuery.data ?? null,
            feedback: previewFeedbackQuery.data ?? [],
            onSubmit: handleSubmitFeedback,
            onWithdraw: handleWithdrawFeedback,
            onIterate: (item) => void handleIterateFromFeedback(item),
            onDisposition: handleFeedbackDisposition,
            diff: bundleDiffQuery.data ?? null,
          }} onExportProduct={() => void handleExportProduct()} onGenerateProduct={() => void handleGenerateProduct()} onPauseGeneration={async () => { const job = selectedGenerationJob; if (job) await refreshAfter(() => pauseGenerationJob({ projectId, jobId: job.job_id })); }} onResumeGeneration={async () => { const job = selectedGenerationJob; if (job) await refreshAfter(async () => { await resumeGenerationJob({ projectId, jobId: job.job_id }); await runGenerationJob({ projectId, jobId: job.job_id }); }); }} onCancelGeneration={async () => { const job = selectedGenerationJob; if (job) await refreshAfter(() => cancelGenerationJob({ projectId, jobId: job.job_id })); }} onCancelExecution={async () => { const job = selectedExecutionJob; if (job) await refreshAfter(() => cancelExecutionJob({ projectId, jobId: job.job_id })); }} onRetryExecution={async () => { const job = selectedExecutionJob; if (job) await refreshAfter(async () => { await retryExecutionJob({ projectId, jobId: job.job_id }); await runExecutionJob({ projectId, jobId: job.job_id }); }); }} sourceModel={{ policy: sourceModelPolicyQuery.data ?? null, savedSourceJob: latestSavedSourceJob, onGenerate: () => void handleGenerateProduct("model"), onRetry: () => void handleRetryModelSource(), onRevalidateSavedDraft: () => void handleRevalidateSavedModelDraft(), onMaterializeSavedSource: (sourceJobId) => void handleMaterializeSavedSource(sourceJobId) }} onExecuteProduct={() => void handleExecuteProduct()} onRepairProduct={() => void handleRepairProduct()} onGenerate={() => handleGenerate("product_theses")} onGenerateWeb={() => handleGenerate("web_generation_contract")} onConfirmWeb={() => {
            const contract = view.web_generation_contract;
            if (!contract) return;
            void refreshAfter(() => confirmWebGenerationContract({ projectId, contractId: contract.web_generation_contract_id, revision: contract.meta.revision }));
          }} /> : null}
          {area === "decisions" ? <DecisionsView view={view} busy={busy} onConfirm={(type) => handleConfirm(view, type)} onThesisTransition={handleThesisTransition} /> : null}
          {area === "evidence" ? <EvidenceView
            view={view}
            busy={busy}
            onDeriveMeasurementPlan={handleDeriveMeasurementPlan}
            onReviseMeasurementPlan={handleMeasurementPlanRevision}
            onConfirmMeasurementPlan={() => handleConfirm(view, "outcome-measurement-plan")}
          /> : null}
          {area === "evidence" && view.outcome_measurement_plan?.status === "confirmed" ? <C1Panel
            projectId={projectId}
            view={view}
            plan={view.outcome_measurement_plan}
            deliveryBundle={deliveryBundlesQuery.data?.at(-1) ?? null}
            executionJob={selectedExecutionJob}
            busy={busy}
            onChanged={async () => { await Promise.all([query.refetch(), deliveryBundlesQuery.refetch(), executionJobsQuery.refetch()]); }}
            onError={setActionError}
          /> : null}
        </div>
      </section>
    </main>
  );
}
