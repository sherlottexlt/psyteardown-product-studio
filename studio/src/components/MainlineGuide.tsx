import type { ProductDeliveryBundle, ProductExecutionJob, ProductGenerationJob, ProductProjectView } from "../api/types";
import { currentStage } from "../domain/project";
import { Badge } from "./Badge";

type GuideArea = "contract" | "workbench" | "decisions" | "evidence";
type GuideState = "done" | "active" | "blocked";

type GuideStep = {
  id: string;
  label: string;
  detail: string;
  area: GuideArea;
  state: GuideState;
};

function stepsFor(
  view: ProductProjectView,
  generationJob: ProductGenerationJob | null,
  executionJob: ProductExecutionJob | null,
  deliveryBundle: ProductDeliveryBundle | null,
): GuideStep[] {
  const intentConfirmed = view.product_intent?.status === "confirmed";
  const problemConfirmed = view.problem_model?.status === "confirmed";
  const outcomeConfirmed = view.outcome_contract?.status === "confirmed";
  const selectedThesis = view.product_theses.some((item) => item.status === "selected");
  const webConfirmed = view.web_generation_contract?.status === "confirmed";
  const bundleMatchesExecution = Boolean(
    deliveryBundle && executionJob && deliveryBundle.execution_job_revision_id === executionJob.revision_id,
  );
  const productVerified = Boolean(bundleMatchesExecution && executionJob?.status === "succeeded");
  const planConfirmed = view.outcome_measurement_plan?.status === "confirmed";
  const understandingReady = intentConfirmed && problemConfirmed && outcomeConfirmed;
  const productPathReady = selectedThesis;
  const implementationReady = webConfirmed;

  return [
    {
      id: "understanding",
      label: "确认要改变的现实",
      detail: understandingReady ? "意图、问题模型和结果边界已确认。" : "先确认提案，不要把模型输出当成事实。",
      area: understandingReady ? "decisions" : "contract",
      state: understandingReady ? "done" : "active",
    },
    {
      id: "path",
      label: "选择一条产品路径",
      detail: productPathReady ? "已有一条具名的人类选择。" : view.product_theses.length ? "比较机制、风险和最低成本证伪方式。" : "先让平台基于已确认结果生成候选路径。",
      area: view.product_theses.length ? "decisions" : "workbench",
      state: productPathReady ? "done" : understandingReady ? "active" : "blocked",
    },
    {
      id: "contract",
      label: "确认可运行产品契约",
      detail: implementationReady ? "Web 契约已确认，生成输入已冻结。" : "核对任务、状态、成功标准和停止/恢复边界。",
      area: "workbench",
      state: implementationReady ? "done" : productPathReady ? "active" : "blocked",
    },
    {
      id: "delivery",
      label: "生成并验证产品",
      detail: productVerified ? "已完成本地构建、预览和浏览器验证。" : generationJob?.status === "failed" || executionJob?.status === "failed" ? "上一次生成或验证失败，先查看安全错误并修复。" : "生成 workspace，再执行 B4，最后导出 B6。",
      area: "workbench",
      state: productVerified ? "done" : implementationReady ? "active" : "blocked",
    },
    {
      id: "experience",
      label: "真实体验并记录结果",
      detail: planConfirmed && productVerified ? "C2 测量计划和当前交付都已具备，可以开始真实任务观察。" : "只有真实任务和明确测量计划都准备好后才进入 C1。",
      area: "evidence",
      state: planConfirmed && productVerified ? "active" : "blocked",
    },
  ];
}

export function MainlineGuide({
  view,
  generationJob = null,
  executionJob = null,
  deliveryBundle = null,
  onNavigate,
  pendingWorkLabel,
  onResumePending,
  pendingWorkBusy = false,
}: {
  view: ProductProjectView;
  generationJob?: ProductGenerationJob | null;
  executionJob?: ProductExecutionJob | null;
  deliveryBundle?: ProductDeliveryBundle | null;
  onNavigate: (area: GuideArea) => void;
  pendingWorkLabel?: string | null;
  onResumePending?: () => void;
  pendingWorkBusy?: boolean;
}) {
  const steps = stepsFor(view, generationJob, executionJob, deliveryBundle);
  const active = steps.find((step) => step.state === "active") ?? steps.at(-1)!;
  const stage = currentStage(view);
  const completed = steps.filter((step) => step.state === "done").length;

  return (
    <section className="mainline-guide" aria-label="产品主链路">
      <div className="mainline-guide__heading">
        <div>
          <p className="eyebrow">主链路 · {completed}/5</p>
          <h2>从现实问题到一次可解释的真实体验</h2>
          <p>只沿一条线推进：理解 → 选择机制 → 生成产品 → 验证 → 真实体验。旁支不会替代当前主线。</p>
        </div>
        <Badge tone={active.state === "active" ? "accent" : "warn"}>{active.label}</Badge>
      </div>
      {pendingWorkLabel && onResumePending ? (
        <div className="recovery-banner" role="status">
          <div><strong>发现未完成工作</strong><small>{pendingWorkLabel} 在上次关闭时没有完成，数据仍然保留。</small></div>
          <button type="button" className="button button--quiet" disabled={pendingWorkBusy} onClick={onResumePending}>{pendingWorkBusy ? "正在恢复…" : "继续这项工作"}</button>
        </div>
      ) : null}
      <ol className="mainline-guide__steps">
        {steps.map((step, index) => (
          <li className={`mainline-guide__step is-${step.state}`} key={step.id}>
            <button type="button" onClick={() => onNavigate(step.area)} aria-label={`主链路第 ${index + 1} 步`}>
              <span className="mainline-guide__number">{step.state === "done" ? "✓" : index + 1}</span>
              <span>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="mainline-guide__next">
        <div>
          <span className="eyebrow">现在只做这一步</span>
          <strong>{active.label}</strong>
          <small>当前工作区阶段：{stage}</small>
        </div>
        <button type="button" className="button button--primary" onClick={() => onNavigate(active.area)}>
          前往下一步
        </button>
      </div>
    </section>
  );
}
