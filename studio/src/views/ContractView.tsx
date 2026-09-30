import { useRef, useState } from "react";
import type {
  EditableOutcomeContract,
  EditableProblemModel,
  EditableProductIntent,
  ProductProjectView,
  ProductProposalJob,
  ProposalJobKind,
  RevisionWriteResult,
} from "../api/types";
import { Badge, statusLabel } from "../components/Badge";
import { OutcomeContractEditor, ProblemModelEditor } from "../components/ContractProposalEditors";
import { EmptyState } from "../components/EmptyState";
import { IntentEditor } from "../components/IntentEditor";
import { ProjectStages } from "../components/ProjectStages";

function ListOrUnknown({ items, unknown = "尚未明确" }: { items: string[]; unknown?: string }) {
  if (!items.length) return <p className="unknown-copy">{unknown}</p>;
  return <ul className="clean-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>;
}

export function ContractView({
  view,
  busy,
  latestJob,
  proposalProvider = "deterministic_fake",
  onProposalProviderChange = () => {},
  onGenerate,
  onRetryLatest,
  onReviseIntent,
  onReviseProblem,
  onReviseOutcome,
}: {
  view: ProductProjectView;
  busy: boolean;
  latestJob: ProductProposalJob | null;
  proposalProvider?: "deterministic_fake" | "real";
  onProposalProviderChange?: (provider: "deterministic_fake" | "real") => void;
  onGenerate: (kind: ProposalJobKind) => Promise<void>;
  onRetryLatest?: () => void;
  onReviseIntent: (draft: EditableProductIntent) => Promise<RevisionWriteResult>;
  onReviseProblem: (draft: EditableProblemModel) => Promise<RevisionWriteResult>;
  onReviseOutcome: (draft: EditableOutcomeContract) => Promise<RevisionWriteResult>;
}) {
  const [editingIntent, setEditingIntent] = useState(false);
  const [editingProblem, setEditingProblem] = useState(false);
  const [editingOutcome, setEditingOutcome] = useState(false);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  function closeEditor() {
    setEditingIntent(false);
    window.requestAnimationFrame(() => editButtonRef.current?.focus());
  }
  const intent = view.product_intent;
  const problem = view.problem_model;
  const contract = view.outcome_contract;
  if (!intent) {
    return (
      <EmptyState
        eyebrow="Product Contract"
        title="还没有形成产品意图"
        description="先从对话与指挥区记录希望改变的现实，再逐步建立问题模型和结果契约。"
      />
    );
  }

  return (
    <div className="view-stack">
      <section className="view-hero">
        <div>
          <p className="eyebrow">Living Product Contract</p>
          <h1>{intent.desired_change}</h1>
          <p>这是面向用户的综合投影。事实、解释、未知和承诺仍作为独立 revision 保存。</p>
        </div>
        <Badge tone={intent.status === "confirmed" ? "good" : "warn"}>{statusLabel(intent.status)}</Badge>
      </section>

      <ProjectStages view={view} />

      <section className="proposal-job-panel" aria-label="Product Contract 提案工作流">
        <div>
          <p className="eyebrow">Product Contract provider</p>
          {!problem && intent.status === "proposed" ? <h2>先确认产品意图</h2> : null}
          {!problem && intent.status === "confirmed" ? <h2>生成可审阅的问题模型提案</h2> : null}
          {problem?.status === "proposed" ? <h2>问题模型等待人类纠正与确认</h2> : null}
          {problem?.status === "confirmed" && !contract ? <h2>生成可审阅的结果契约提案</h2> : null}
          {contract?.status === "proposed" ? <h2>结果契约等待价值边界审查</h2> : null}
          {contract?.status === "confirmed" ? <h2>Product Contract 已形成</h2> : null}
          <p>{proposalProvider === "real" ? "真实 DeepSeek 会生成可审阅 proposal；模型输出仍不是外部事实或用户结果。" : "默认使用无网络 fake provider 验证 proposal/confirm 工作流；真实 DeepSeek 输出仍必须由你审阅确认，不是外部事实、证据或用户结果。"}</p>
          <label className="inline-control">
            <span>提案 provider</span>
            <select value={proposalProvider} onChange={(event) => onProposalProviderChange(event.target.value as "deterministic_fake" | "real")} disabled={busy}>
              <option value="deterministic_fake">fake（离线）</option>
              <option value="real">real（DeepSeek）</option>
            </select>
          </label>
          {latestJob ? <div className="proposal-job-panel__meta"><Badge tone={latestJob.status === "succeeded" ? "good" : latestJob.status === "failed" || latestJob.status === "stale_input" ? "danger" : "warn"}>{statusLabel(latestJob.status)}</Badge><span>{latestJob.kind} · {latestJob.provider}@{latestJob.provider_version} · attempt {latestJob.attempt}</span>{latestJob.status === "failed" || latestJob.status === "stale_input" ? <button className="button button--quiet" type="button" disabled={busy} onClick={onRetryLatest}>{busy ? "正在重试…" : "带着错误重试"}</button> : null}</div> : null}
        </div>
        {!problem && intent.status === "confirmed" ? <button className="button button--primary" disabled={busy} onClick={() => void onGenerate("problem_model")}>{busy ? "正在推进…" : "生成问题模型提案"}</button> : null}
        {problem?.status === "confirmed" && !contract ? <button className="button button--primary" disabled={busy} onClick={() => void onGenerate("outcome_contract")}>{busy ? "正在推进…" : "生成结果契约提案"}</button> : null}
      </section>

      {editingIntent ? (
        <IntentEditor
          intent={intent}
          busy={busy}
          onCancel={closeEditor}
          onSave={onReviseIntent}
        />
      ) : null}
      {editingProblem && problem ? <ProblemModelEditor problem={problem} busy={busy} onCancel={() => setEditingProblem(false)} onSave={onReviseProblem} /> : null}
      {editingOutcome && contract ? <OutcomeContractEditor contract={contract} busy={busy} onCancel={() => setEditingOutcome(false)} onSave={onReviseOutcome} /> : null}

      <div className="contract-grid">
        <section className="panel contract-card contract-card--wide">
          <div className="panel__heading">
            <div><p className="eyebrow">01 · Intent</p><h2>为谁，改变什么</h2></div>
            <div className="panel__actions">
              <span className="revision">r{intent.meta.revision}</span>
              <button ref={editButtonRef} className="text-action" onClick={() => setEditingIntent(true)} type="button">
                纠正产品意图
              </button>
            </div>
          </div>
          <p className="contract-promise">{intent.desired_change}</p>
          <dl className="definition-grid">
            <div><dt>受到影响的人</dt><dd>{intent.affected_people.join(" · ")}</dd></div>
            <div><dt>当前情境</dt><dd>{intent.current_situation || "尚未补充"}</dd></div>
          </dl>
        </section>

        <section className="panel contract-card">
          <div className="panel__heading"><div><p className="eyebrow">Boundaries</p><h2>明确不做什么</h2></div></div>
          <ListOrUnknown items={intent.explicit_non_goals} unknown="尚未记录明确拒绝项" />
        </section>

        <section className="panel contract-card">
          <div className="panel__heading"><div><p className="eyebrow">Constraints</p><h2>已知约束</h2></div></div>
          <ListOrUnknown items={intent.known_constraints} unknown="约束仍待识别" />
        </section>

        <section className="panel contract-card contract-card--wide">
          <div className="panel__heading">
            <div><p className="eyebrow">02 · Problem model</p><h2>目前如何理解现实</h2></div>
            {problem ? <div className="panel__actions"><Badge tone={problem.status === "confirmed" ? "good" : "warn"}>{statusLabel(problem.status)}</Badge><span className="revision">r{problem.meta.revision}</span><button className="text-action" onClick={() => setEditingProblem(true)}>纠正问题模型</button></div> : null}
          </div>
          {problem ? (
            <div className="model-columns">
              <div><h3>有来源的事实</h3><ListOrUnknown items={problem.facts.map((item) => item.statement)} /></div>
              <div><h3>竞争性解释</h3><ListOrUnknown items={problem.competing_explanations.map((item) => item.statement)} /></div>
              <div>
                <h3>仍未知</h3>
                <ListOrUnknown items={problem.unknowns.map((item) => item.question)} />
                <p className="unknown-copy">这些是可能改变产品方向、但目前还不知道答案的问题；不必全部回答，也不会阻止生成结果契约。知道答案时可在“纠正问题模型”里补充为事实。</p>
              </div>
            </div>
          ) : <p className="unknown-copy">问题模型尚未形成。当前意图不会被包装成已经理解的问题。</p>}
        </section>

        <section className="panel contract-card contract-card--wide">
          <div className="panel__heading">
            <div><p className="eyebrow">03 · Outcome contract</p><h2>怎样才算产生了结果</h2></div>
            {contract ? <div className="panel__actions"><Badge tone={contract.status === "confirmed" ? "good" : "warn"}>{statusLabel(contract.status)}</Badge><span className="revision">r{contract.meta.revision}</span><button className="text-action" onClick={() => setEditingOutcome(true)}>纠正结果契约</button></div> : null}
          </div>
          {contract ? (
            <div className="outcome-layout">
              <div className="outcome-primary">
                <h3>目标结果</h3>
                <ListOrUnknown items={contract.target_outcomes.map((item) => item.description)} />
              </div>
              <dl className="definition-grid definition-grid--three">
                <div><dt>适用人群</dt><dd>{contract.target_segments.join(" · ") || "未明确"}</dd></div>
                <div><dt>适用情境</dt><dd>{contract.applicable_contexts.join(" · ") || "未明确"}</dd></div>
                <div><dt>最低交付层级</dt><dd>{statusLabel(contract.minimum_delivery_maturity)}</dd></div>
              </dl>
              <div className="indicator-list">
                {contract.success_indicators.map((indicator) => (
                  <article key={indicator.indicator_id}>
                    <span className="indicator-list__signal" />
                    <div><h3>{indicator.operational_definition}</h3><p>{indicator.observation_method} · {indicator.threshold_or_target}</p></div>
                    <Badge>{statusLabel(indicator.required_evidence)}</Badge>
                  </article>
                ))}
              </div>
              <div className="model-columns">
                <div><h3>禁止结果</h3><ListOrUnknown items={contract.prohibited_outcomes.map((item) => item.description)} unknown="尚未列出；仍需人工明确审查" /></div>
                <div><h3>停止条件</h3><ListOrUnknown items={contract.stop_conditions.map((item) => item.condition)} /></div>
                <div><h3>现实证据要求</h3><ListOrUnknown items={contract.required_real_world_evidence} /></div>
              </div>
            </div>
          ) : <p className="unknown-copy">结果标准、禁止结果和停止条件尚未建立，因此还不能扩大生成。</p>}
        </section>
      </div>
    </div>
  );
}
