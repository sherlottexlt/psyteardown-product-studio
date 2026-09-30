import type { ProductGenerationJob, ProductProjectView } from "../api/types";
import { Badge, statusLabel } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { FeedbackDispositionControls, PreviewFeedbackPanel, type PreviewFeedbackDraft } from "./PreviewFeedbackPanel";

type DeliveryBundleDiff = import("../api/types").DeliveryBundleDiff;
type PreviewFeedback = import("../api/types").PreviewFeedback;
type PreviewFeedbackDisposition = import("../api/types").PreviewFeedbackDisposition;

const fileChangeLabels = { added: "新增", removed: "删除", modified: "变化", unchanged: "未变" } as const;

function BundleDiffPanel({
  diff,
  sourceFeedback,
  busy,
  onDisposition,
}: {
  diff: DeliveryBundleDiff;
  sourceFeedback: PreviewFeedback[];
  busy: boolean;
  onDisposition?: (item: PreviewFeedback, disposition: PreviewFeedbackDisposition) => void;
}) {
  const changed = diff.files.filter((item) => item.change !== "unchanged");
  const productChanged = changed.some((item) => item.path.startsWith("source/") || item.path.startsWith("build/"));
  return (
    <section className="panel bundle-diff" aria-label="交付版本差异">
      <div className="panel__heading">
        <div><p className="eyebrow">Revision diff</p><h2>{diff.base_bundle_id} → {diff.target_bundle_id}</h2></div>
        <Badge tone={productChanged ? "accent" : "warn"}>{productChanged ? "源码/构建有变化" : "源码与构建未变化"}</Badge>
      </div>
      <p className="unknown-copy">
        契约 {diff.base_contract_revision_id} → {diff.target_contract_revision_id}。只比较记录的文件 sha256，不做逐行或语义差异。
        {productChanged ? null : " 当前模板不读取新增的验收检查，所以产品本身没有改变；需要模型生成或人工修改才会体现在源码中。"}
      </p>
      <div className="bundle-diff__columns">
        <div>
          <h3>契约变化 · {diff.contract_changes.length}</h3>
          {diff.contract_changes.length ? <ul>{diff.contract_changes.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="unknown-copy">两个交付包使用同一契约 revision。</p>}
        </div>
        <div>
          <h3>文件变化 · {changed.length} / {diff.files.length}</h3>
          <ul>{changed.map((item) => <li key={item.path}><Badge tone={item.change === "removed" ? "danger" : "neutral"}>{fileChangeLabels[item.change]}</Badge> <code>{item.path}</code></li>)}</ul>
        </div>
      </div>
      {sourceFeedback.length ? (
        <div className="bundle-diff__feedback">
          <h3>这次迭代来源的反馈</h3>
          <ul>
            {sourceFeedback.map((item) => (
              <li key={item.feedback_id}>
                <small>{item.feedback_id}</small>
                <p>{item.status === "withdrawn" ? "正文已按撤回清除。" : item.text}</p>
                {item.status === "submitted" && onDisposition ? <FeedbackDispositionControls item={item} busy={busy} onDisposition={onDisposition} /> : null}
              </li>
            ))}
          </ul>
          <p className="unknown-copy">是否采纳由你标记，平台不会根据生成结果自动推断。</p>
        </div>
      ) : null}
    </section>
  );
}

export function WorkbenchView({
  view,
  busy,
  onGenerate,
  onGenerateWeb,
  onConfirmWeb,
  generationJob,
  executionJob,
  repairJob,
  deliveryBundle,
  deliveryArchiveUrl,
  onGenerateProduct,
  onExecuteProduct,
  onRepairProduct,
  onExportProduct,
  onPauseGeneration,
  onResumeGeneration,
  onCancelGeneration,
  onCancelExecution,
  onRetryExecution,
  preview,
  sourceModel,
}: {
  view: ProductProjectView;
  busy: boolean;
  onGenerate: () => void;
  onGenerateWeb: () => void;
  onConfirmWeb: () => void;
  generationJob?: import("../api/types").ProductGenerationJob | null;
  executionJob?: import("../api/types").ProductExecutionJob | null;
  repairJob?: import("../api/types").ProductRepairJob | null;
  deliveryBundle?: import("../api/types").ProductDeliveryBundle | null;
  deliveryArchiveUrl?: (bundleId: string) => string;
  onGenerateProduct: () => void;
  onExecuteProduct: () => void;
  onRepairProduct: () => void;
  onExportProduct?: () => void;
  onPauseGeneration?: () => Promise<void>;
  onResumeGeneration?: () => Promise<void>;
  onCancelGeneration?: () => Promise<void>;
  onCancelExecution?: () => Promise<void>;
  onRetryExecution?: () => Promise<void>;
  preview?: {
    url: (bundleId: string) => string;
    policy: import("../api/types").PreviewFeedbackPolicy | null;
    feedback: import("../api/types").PreviewFeedback[];
    onSubmit: (bundleId: string, draft: PreviewFeedbackDraft) => Promise<boolean>;
    onWithdraw: (item: import("../api/types").PreviewFeedback) => void;
    onIterate?: (item: PreviewFeedback) => void;
    onDisposition?: (item: PreviewFeedback, disposition: PreviewFeedbackDisposition) => void;
    diff?: DeliveryBundleDiff | null;
  };
  sourceModel?: {
    policy: import("../api/types").SourceModelPolicy | null;
    onGenerate: () => void;
    onRetry: () => void;
    savedSourceJob?: ProductGenerationJob | null;
    onRevalidateSavedDraft?: () => void;
    onMaterializeSavedSource?: (sourceJobId: string) => void;
  };
}) {
  const modelJob = generationJob?.materialization_kind === "model" ? generationJob : null;
  const savedSourceJob = generationJob?.materialization_kind === "saved_model" ? generationJob : null;
  const modelPolicy = sourceModel?.policy ?? null;
  const primaryFlowTasks = (view.web_generation_contract?.primary_flow_task_ids ?? [])
    .map((taskId) => view.web_generation_contract?.tasks.find((task) => task.task_id === taskId))
    .filter((task): task is NonNullable<typeof task> => Boolean(task));
  const bundleMatchesExecution = Boolean(
    deliveryBundle && executionJob && deliveryBundle.execution_job_revision_id === executionJob.revision_id,
  );
  const unsupportedRepairForCurrentExecution = Boolean(
    executionJob &&
    repairJob?.execution_job_id === executionJob.job_id &&
    repairJob.attempts.some(
      (attempt) => attempt.status === "unsupported" || attempt.error_code === "unsupported_failure",
    ),
  );
  if (!view.product_theses.length) {
    return (
      <EmptyState
        eyebrow="Product workbench"
        title="先比较几条真正不同的产品路径"
        description={view.outcome_contract?.status === "confirmed"
          ? "结果契约已经确认。平台会生成三条机制不同、可证伪且保留未知的候选；这不是研究结论，也不会自动选择赢家。"
          : "产品论点尚未形成。先确认结果契约，平台才会进入差异化路径搜索。"}
        action={view.outcome_contract?.status === "confirmed" ? (
          <button className="button button--primary" disabled={busy} onClick={onGenerate}>
            {busy ? "正在生成候选…" : "生成 3 条产品论点"}
          </button>
        ) : null}
      />
    );
  }
  return (
    <div className="view-stack">
      <section className="view-hero">
        <div><p className="eyebrow">Product workbench</p><h1>产品论点与实现分支</h1><p>这些路径保留各自的机制、未知和证伪方式，不通过总分强行合并。</p></div>
        <div className="panel__actions">
          <Badge tone="accent">{view.product_theses.length} 条路径</Badge>
          {view.product_theses.some((thesis) => thesis.status === "exploring" || thesis.status === "selected") ? (
            <button className="button button--primary" disabled={busy} onClick={onGenerateWeb}>
              {busy ? "正在准备契约…" : view.web_generation_contract ? "重新生成 Web 契约提案" : "生成 Web 契约"}
            </button>
          ) : null}
        </div>
      </section>
      <div className="thesis-grid">
        {view.product_theses.map((thesis, index) => (
          <article className={`thesis-card ${thesis.status === "selected" ? "is-selected" : ""}`} key={thesis.thesis_id}>
            <header><span className="thesis-card__index">0{index + 1}</span><Badge tone={thesis.status === "selected" ? "good" : thesis.status === "rejected" ? "danger" : "neutral"}>{statusLabel(thesis.status)}</Badge></header>
            <h2>{thesis.name}</h2>
            <p className="thesis-card__promise">{thesis.product_promise}</p>
            <div className="thesis-card__modes">{thesis.realization_modes.map((mode) => <span key={mode}>{mode}</span>)}</div>
            <dl>
              <div><dt>差异</dt><dd>{thesis.differentiation}</dd></div>
              <div><dt>最大未知</dt><dd>{thesis.key_unknowns[0]}</dd></div>
              <div><dt>最低成本证伪</dt><dd>{thesis.falsifiable_predictions[0]?.cheapest_test ?? "待定义"}</dd></div>
              <div><dt>验证层级</dt><dd>{statusLabel(thesis.validation_strategy[0]?.evidence_level ?? "unknown")}</dd></div>
              <div><dt>交付负担</dt><dd>{thesis.delivery_estimate.maintenance_burden}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      {bundleMatchesExecution && deliveryBundle && preview ? (
        <PreviewFeedbackPanel
          key={deliveryBundle.bundle_id}
          bundle={deliveryBundle}
          contract={view.web_generation_contract ?? null}
          previewUrl={preview.url(deliveryBundle.bundle_id)}
          policy={preview.policy}
          feedback={preview.feedback.filter((item) => item.delivery_bundle_id === deliveryBundle.bundle_id)}
          busy={busy}
          onSubmit={(draft) => preview.onSubmit(deliveryBundle.bundle_id, draft)}
          onWithdraw={preview.onWithdraw}
          onIterate={preview.onIterate}
          onDisposition={preview.onDisposition}
        />
      ) : (
        <section className="preview-frame">
          <div className="preview-frame__bar"><span /><span /><span /><p>Runnable product preview</p><Badge tone="warn">尚未交付</Badge></div>
          <div className="preview-frame__empty"><div className="preview-glyph">↗</div><h2>还没有可预览的交付构建</h2><p>完成生成、隔离构建与浏览器验证并导出交付包后，已交付的构建物会在这里打开，你可以对页面和任务留下反馈。</p></div>
        </section>
      )}
      {preview?.diff ? (
        <BundleDiffPanel
          diff={preview.diff}
          sourceFeedback={preview.feedback.filter((item) =>
            view.web_generation_contract?.source_refs.some(
              (ref) => ref.source_type === "preview_feedback" && ref.source_id === item.feedback_id,
            ),
          )}
          busy={busy}
          onDisposition={preview.onDisposition}
        />
      ) : null}
      {view.web_generation_contract ? (
        <section className="panel contract-card contract-card--wide" aria-label="Web 生成契约">
          <div className="panel__heading">
            <div><p className="eyebrow">Web generation contract</p><h2>{view.web_generation_contract.app_title}</h2></div>
            <Badge tone={view.web_generation_contract.status === "confirmed" ? "good" : "warn"}>{statusLabel(view.web_generation_contract.status)}</Badge>
          </div>
          <dl className="definition-grid definition-grid--three">
            <div><dt>模板</dt><dd>{view.web_generation_contract.template_id} · {view.web_generation_contract.template_version}</dd></div>
            <div><dt>页面 / 任务</dt><dd>{view.web_generation_contract.screens.length} / {view.web_generation_contract.tasks.length}</dd></div>
            <div><dt>运行边界</dt><dd>local fixture only · no network</dd></div>
          </dl>
          {primaryFlowTasks.length ? (
            <div className="primary-flow-summary" aria-label="主体验路径">
              <div><p className="eyebrow">Primary journey</p><h3>真实使用只沿这条路径</h3></div>
              <ol>{primaryFlowTasks.map((task, index) => <li key={task.task_id}><span>{index + 1}</span><div><strong>{task.goal}</strong><small>{task.success_criteria}</small></div></li>)}</ol>
              <p>先完成这条连续路径，再看旁支按钮；它是后续真实任务观察的唯一主链路。</p>
            </div>
          ) : null}
          <div className="contract-screens" aria-label="契约页面明细">
            <div className="contract-screens__heading"><div><p className="eyebrow">Proposed pages</p><h3>这就是 r{view.web_generation_contract.meta?.revision ?? 1} 会生成的页面</h3></div><span>确认前只读预览</span></div>
            <div className="contract-screens__grid">
              {view.web_generation_contract.screens.map((screen, index) => (
                <article className="contract-screen-card" key={screen.screen_id}>
                  <header><span>{String(index + 1).padStart(2, "0")}</span><h4>{screen.title}</h4></header>
                  <p>{screen.purpose}</p>
                  <ul>{screen.task_ids.map((taskId) => {
                    const task = view.web_generation_contract?.tasks.find((item) => item.task_id === taskId);
                    return <li key={taskId}><strong>{task?.goal ?? taskId}</strong>{task?.success_criteria ? <small>{task.success_criteria}</small> : null}</li>;
                  })}</ul>
                </article>
              ))}
            </div>
            <p className="unknown-copy">这些是 Web 契约中的页面定义，不是已经生成的源码或 ZIP。确认契约后，才会生成可运行 workspace。</p>
          </div>
          <p className="unknown-copy">这是待确认的生成输入，不是源码、运行实例或真实结果。确认后仍需 B3 的 workspace、预算和沙箱 Gate。</p>
          {view.web_generation_contract.status === "proposed" && view.web_generation_contract.meta.revision > 1 ? (
            <p className="unknown-copy">
              这是 r{view.web_generation_contract.meta?.revision ?? 1} 修订提案
              {(view.web_generation_contract.source_refs ?? []).filter((ref) => ref.source_type === "preview_feedback").at(-1)
                ? `，来源预览反馈 ${(view.web_generation_contract.source_refs ?? []).filter((ref) => ref.source_type === "preview_feedback").at(-1)?.source_id}`
                : ""}
              。确认前请核对新增的验收检查；反馈本身不会因此改变状态。
            </p>
          ) : null}
          {view.web_generation_contract.status === "proposed" ? (
            <button className="button button--primary" disabled={busy} onClick={onConfirmWeb}>确认 Web 生成契约</button>
          ) : null}
          {view.web_generation_contract.status === "confirmed" ? (
            <div className="panel__actions">
              <button className="button button--primary" disabled={busy} onClick={onGenerateProduct}>
                {busy ? "正在生成 workspace…" : "生成受限 Web workspace"}
              </button>
              {sourceModel ? (
                <button className="button button--quiet" disabled={busy || !modelPolicy?.available} onClick={sourceModel.onGenerate}>
                  {modelPolicy?.available ? `用模型写源码 · ${modelPolicy.provider} ${modelPolicy.model}` : "模型写源码（未配置）"}
                </button>
              ) : null}
              {generationJob ? <Badge tone={generationJob.status === "succeeded" ? "good" : generationJob.status === "failed" || generationJob.status === "budget_exhausted" ? "danger" : "warn"}>{generationJob.status} · {generationJob.consumed_files} files</Badge> : null}
              {generationJob && ["queued", "running"].includes(generationJob.status) ? <>
                {onPauseGeneration ? <button className="button button--quiet" disabled={busy} onClick={() => void onPauseGeneration()}>暂停</button> : null}
                {onCancelGeneration ? <button className="button button--quiet" disabled={busy} onClick={() => void onCancelGeneration()}>取消</button> : null}
              </> : null}
              {generationJob?.status === "paused" ? <>
                {onResumeGeneration ? <button className="button button--quiet" disabled={busy} onClick={() => void onResumeGeneration()}>继续生成</button> : null}
                {onCancelGeneration ? <button className="button button--quiet" disabled={busy} onClick={() => void onCancelGeneration()}>取消</button> : null}
              </> : null}
            </div>
          ) : null}
          {sourceModel && view.web_generation_contract.status === "confirmed" ? (
            <p className="unknown-copy">
              {modelPolicy?.available
                ? `模型只收到已确认的 Web 契约，不会收到原始输入、问题模型、结果契约或论题；它只写 ${modelPolicy.model_writes.join("、")}，每个 job 最多 ${modelPolicy.max_calls_per_job} 次调用，请求与响应全文只保存在本机。测试由契约派生，模型不能修改。`
                : "未配置源码模型：启动 API 前设置 PSYTEARDOWN_PRODUCT_SOURCE_MODEL=deepseek 与 DEEPSEEK_API_KEY。"}
            </p>
          ) : null}
          {generationJob?.materialization_kind === "template" ? <p className="unknown-copy">B3 本地边界：{generationJob.sandbox.network_policy} network · {generationJob.sandbox.execution_policy} · budget {generationJob.consumed_bytes}/{generationJob.budget.max_bytes} bytes。源码尚未执行或预览。</p> : null}
          {modelJob || savedSourceJob ? (
            <section className="model-calls" aria-label="模型调用记录">
              <p className="unknown-copy">B7m 模型源码：App.tsx 与 styles.css 由模型写出并通过静态门禁才落盘；其余模板文件固定；尚未经人审阅，需 B4 真实验证后才能导出。</p>
              {savedSourceJob && sourceModel?.onMaterializeSavedSource ? (
                <div>
                  <p className="unknown-copy">此源码源自本机静态复核通过的模型响应。可以保留当前 workspace，再按最新平台验证契约创建独立 lineage。</p>
                  <button className="button button--quiet" disabled={busy} onClick={() => sourceModel.onMaterializeSavedSource?.(savedSourceJob.job_id)}>从原始已保存源码再建 workspace（不调用模型）</button>
                </div>
              ) : null}
              {modelJob ? <ol>
                {modelJob.model_calls.map((call) => (
                  <li key={call.attempt}>
                    <Badge tone={call.outcome === "accepted" || call.static_gate_revalidated ? "good" : "warn"}>
                      {call.static_gate_revalidated ? "本地复核通过（provider 原始结果保留）" : call.outcome}
                    </Badge>
                    <span>第 {call.attempt} 次 · {call.provider} {call.model} · {call.input_tokens ?? "?"}/{call.output_tokens ?? "?"} tokens · {call.duration_seconds.toFixed(1)}s{call.static_gate_version ? ` · ${call.static_gate_version}` : ""}</span>
                    {call.rejection_reasons.length ? <ul>{call.rejection_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}
                  </li>
                ))}
              </ol> : <p className="unknown-copy">此 workspace 由已保存并通过本地静态门禁的源码派生，来源生成 Job：{savedSourceJob?.source_generation_job_id} · {savedSourceJob?.source_generation_job_revision_id}。本次没有调用 provider。</p>}
              {sourceModel && modelJob?.status === "succeeded" && modelJob.model_calls.at(-1)?.static_gate_revalidated && sourceModel.onMaterializeSavedSource ? (
                <div>
                  <p className="unknown-copy">创建独立的新 generation job 和 workspace，复制 manifest 校验过的 App.tsx/styles.css，重新生成当前平台测试与固定文件；旧 job、workspace 和执行记录保持不变，不调用模型。</p>
                  <button className="button button--primary" disabled={busy} onClick={() => sourceModel.onMaterializeSavedSource?.(modelJob.job_id)}>从已验证源码创建新 workspace（不调用模型）</button>
                </div>
              ) : null}
              {sourceModel && modelJob?.status === "failed" && modelJob.attempt < modelJob.budget.max_attempts ? (
                <button className="button button--quiet" disabled={busy} onClick={sourceModel.onRetry}>带上门禁原因重试（剩余 {modelJob.budget.max_attempts - modelJob.attempt} 次）</button>
              ) : null}
              {sourceModel && modelJob?.status === "failed" && modelJob.model_calls.at(-1)?.outcome === "rejected" && sourceModel.onRevalidateSavedDraft ? (
                <div>
                  <p className="unknown-copy">可直接用本机已保存的模型草稿重新运行当前静态检查；不会再次调用模型，也不会覆盖这条失败记录。</p>
                  <button className="button button--primary" disabled={busy} onClick={sourceModel.onRevalidateSavedDraft}>用已保存草稿重新校验（不调用模型）</button>
                </div>
              ) : null}
            </section>
          ) : null}
          {generationJob?.status === "succeeded" ? (
            <div className="panel__actions">
              <button className="button button--quiet" disabled={busy} onClick={onExecuteProduct}>
                {busy ? "正在执行 sandbox…" : "构建并验证 workspace"}
              </button>
              {executionJob ? <Badge tone={executionJob.status === "succeeded" ? "good" : "warn"}>{executionJob.status} · {executionJob.checkpoint_step ?? "queued"}</Badge> : null}
            </div>
          ) : null}
          {executionJob ? <>
            <p className="unknown-copy">B4 执行边界：依赖安装、构建、loopback 预览与 Chromium/axe 检查；无 Secret，运行时无外网。执行日志仅保留安全摘要。</p>
            {executionJob.status === "failed" && executionJob.error_code === "browser_test_harness_failed" ? (
              <p className="form-error" role="alert">构建和预览已通过，但平台生成的契约浏览器测试脚本自身异常；这不等同于产品源码缺陷。平台修复后请重新生成一个 workspace 再验证，不要对原源码盲目打补丁。</p>
            ) : null}
            {executionJob.status === "failed" && savedSourceJob && executionJob.generation_job_id === savedSourceJob.job_id ? (
              <p className="unknown-copy">这次验证针对独立新建的 saved-source workspace，旧 generation 与 B4 执行记录均保留。可查看本次 browser checkpoint 错误；不要把测试失败误认为旧 workspace 被覆盖。</p>
            ) : null}
            <div className="panel__actions">
              {executionJob.status === "running" && onCancelExecution ? <button className="button button--quiet" disabled={busy} onClick={() => void onCancelExecution()}>停止验证</button> : null}
              {["failed", "budget_exhausted", "stale_input"].includes(executionJob.status) && onRetryExecution ? <button className="button button--quiet" disabled={busy} onClick={() => void onRetryExecution()}>重试验证</button> : null}
            </div>
          </> : null}
          {executionJob && ["failed", "budget_exhausted"].includes(executionJob.status) && !unsupportedRepairForCurrentExecution ? (
            <div className="panel__actions">
              <button className="button button--quiet" disabled={busy} onClick={onRepairProduct}>
                {busy ? "正在准备修复…" : "定位并尝试受限修复"}
              </button>
              {repairJob ? <Badge tone={repairJob.status === "succeeded" ? "good" : "warn"}>{repairJob.status} · {repairJob.attempts.length} attempts</Badge> : null}
            </div>
          ) : null}
          {unsupportedRepairForCurrentExecution ? (
            <p className="form-error" role="status">确定性修复器没有适用于这类浏览器失败的白名单补丁，原 workspace 源码未被修改；系统不会再重复消耗修复尝试。若这是平台测试脚本问题，请重启已更新的 API，再明确重新生成 workspace 并重新验证。</p>
          ) : null}
          {repairJob ? (
            <>
              <p className="unknown-copy">B5 只允许确定性白名单补丁；原始 workspace 保持不变。每次诊断、补丁、验证 Job 与成本都会保留。</p>
              {repairJob.attempts.at(-1) ? (
                <dl className="definition-grid definition-grid--three">
                  <div><dt>最近诊断</dt><dd>{repairJob.attempts.at(-1)?.diagnosis}</dd></div>
                  <div><dt>尝试成本</dt><dd>{repairJob.attempts.at(-1)?.cost_units} / {repairJob.budget.max_cost_units} units</dd></div>
                  <div><dt>补丁 / 验证</dt><dd>{repairJob.attempts.at(-1)?.patches.length} patches · {repairJob.attempts.at(-1)?.output_execution_job_id ?? "not started"}</dd></div>
                  {repairJob.error_code ? <div><dt>安全错误</dt><dd>{repairJob.error_code}</dd></div> : null}
                </dl>
              ) : null}
            </>
          ) : null}
          {executionJob?.status === "succeeded" && onExportProduct ? (
            <div className="panel__actions">
              <button className="button button--quiet" disabled={busy} onClick={onExportProduct}>
                {busy ? "正在打包…" : bundleMatchesExecution ? "重新获取交付包" : "导出交付包"}
              </button>
              {bundleMatchesExecution && deliveryBundle ? <Badge tone="good">{deliveryBundle.files.length} files · {Math.ceil(deliveryBundle.archive_bytes / 1024)} KiB</Badge> : null}
            </div>
          ) : null}
          {bundleMatchesExecution && deliveryBundle ? (
            <section aria-label="交付包">
              <dl className="definition-grid definition-grid--three">
                <div><dt>包 sha256</dt><dd><code>{deliveryBundle.archive_sha256.slice(0, 16)}…</code></dd></div>
                <div><dt>来源</dt><dd>{deliveryBundle.materialization_kind === "repair" ? "B5 修复 lineage" : deliveryBundle.materialization_kind === "model" ? "B7m 模型写源码" : "B3 模板生成"} · {deliveryBundle.execution_job_revision_id}</dd></div>
                <div><dt>结果证据</dt><dd>{deliveryBundle.outcome_evidence_level}</dd></div>
              </dl>
              {deliveryArchiveUrl ? <a className="button button--primary" href={deliveryArchiveUrl(deliveryBundle.bundle_id)} download>下载交付包 (.zip)</a> : null}
              <p className="unknown-copy">下一步：继续体验和提交反馈，请使用上方的交付构建预览；下载的 ZIP 只是保存/分享交付物。若要在本机单独打开，解压后用静态 HTTP 服务运行 `build/`，不要双击 `build/index.html`，详见包内 `DELIVERY.md`。</p>
              <p className="unknown-copy">交付包只证明本机覆盖范围内的软件验证。未验证声明：</p>
              <ul className="unknown-copy">{deliveryBundle.unverified_claims.map((claim) => <li key={claim}>{claim}</li>)}</ul>
            </section>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
