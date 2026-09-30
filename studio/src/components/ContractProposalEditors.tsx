import { type FormEvent, useEffect, useRef, useState } from "react";
import type {
  EditableOutcomeContract,
  EditableProblemModel,
  OutcomeContract,
  ProblemModel,
  RevisionWriteResult,
} from "../api/types";

const splitLines = (value: string) =>
  value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
const splitPeople = (value: string) =>
  value.split(/[,，、\r\n]/).map((item) => item.trim()).filter(Boolean);

function ResultMessage({ result }: { result: RevisionWriteResult | null }) {
  if (!result || result.status === "saved") return null;
  const message =
    result.status === "conflict"
      ? `服务端已有更新，已刷新到 r${result.latestRevision}。草稿仍保留，请复核后重试。`
      : result.message;
  return <p className="intent-editor__message" role="alert">{message}</p>;
}

export function ProblemModelEditor({
  problem,
  busy,
  onCancel,
  onSave,
}: {
  problem: ProblemModel;
  busy: boolean;
  onCancel: () => void;
  onSave: (draft: EditableProblemModel) => Promise<RevisionWriteResult>;
}) {
  const [facts, setFacts] = useState(problem.facts.map((item) => item.statement).join("\n"));
  const [explanations, setExplanations] = useState(
    problem.competing_explanations.map((item) => item.statement).join("\n"),
  );
  const [unknowns, setUnknowns] = useState(problem.unknowns.map((item) => item.question).join("\n"));
  const [result, setResult] = useState<RevisionWriteResult | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => titleRef.current?.focus(), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next = await onSave({
      facts: splitLines(facts),
      explanations: splitLines(explanations),
      unknowns: splitLines(unknowns),
    });
    setResult(next);
    if (next.status === "saved") onCancel();
  }
  const valid = splitLines(facts).length > 0 && splitLines(explanations).length >= 2;
  return (
    <form className="intent-editor" onSubmit={(event) => void submit(event)}>
      <header><div><p className="eyebrow">Correct proposal</p><h3 ref={titleRef} tabIndex={-1}>纠正问题模型</h3><p>事实只写你能确认的内容；竞争解释不是事实。未知是待查问题，不是必须答完的问卷。</p></div><span className="revision">基于 r{problem.meta.revision}</span></header>
      <aside className="recovery-banner" role="note" aria-label="如何处理仍未知的问题">
        <div>
          <strong>知道答案：把它写进“有来源的事实”，并从“仍未知”移除已解决的问题。</strong>
          <small>暂时不知道：保留问题即可，不要猜。你不需要清空“仍未知”才能确认问题模型或生成结果契约；结果契约提案失败也不是因为未知没有答完。</small>
        </div>
      </aside>
      <div className="intent-editor__grid">
        <label>有来源的事实<textarea rows={6} value={facts} onChange={(event) => setFacts(event.target.value)} /><small>每行一项；只写你亲自知道/观察到的答案，保存后标记为本次用户纠正的来源</small></label>
        <label>仍未知<textarea rows={6} value={unknowns} onChange={(event) => setUnknowns(event.target.value)} /><small>每行一个尚未解决、可能影响产品方向的问题；不知道答案就保留</small></label>
        <label className="intent-editor__wide">竞争性解释<textarea rows={6} value={explanations} onChange={(event) => setExplanations(event.target.value)} /><small>确认至少保留两个真实不同、可被证伪的解释</small></label>
      </div>
      <ResultMessage result={result} />
      <footer><span>保存会创建新的 proposed revision</span><div><button className="button button--quiet" onClick={onCancel} disabled={busy} type="button">取消</button><button className="button button--primary" disabled={busy || !valid}>保存问题提案</button></div></footer>
    </form>
  );
}

export function OutcomeContractEditor({
  contract,
  busy,
  onCancel,
  onSave,
}: {
  contract: OutcomeContract;
  busy: boolean;
  onCancel: () => void;
  onSave: (draft: EditableOutcomeContract) => Promise<RevisionWriteResult>;
}) {
  const indicator = contract.success_indicators[0];
  const [targetSegments, setTargetSegments] = useState(contract.target_segments.join("，"));
  const [contexts, setContexts] = useState(contract.applicable_contexts.join("\n"));
  const [targetOutcome, setTargetOutcome] = useState(contract.target_outcomes[0]?.description ?? "");
  const [indicatorDefinition, setIndicatorDefinition] = useState(indicator?.operational_definition ?? "");
  const [observationMethod, setObservationMethod] = useState(indicator?.observation_method ?? "");
  const [threshold, setThreshold] = useState(indicator?.threshold_or_target ?? "");
  const [prohibited, setProhibited] = useState(contract.prohibited_outcomes.map((item) => item.description).join("\n"));
  const [timeBudget, setTimeBudget] = useState(contract.resource_boundary.time_budget ?? "");
  const [dataBoundary, setDataBoundary] = useState(contract.resource_boundary.data_boundary ?? "");
  const [stopCondition, setStopCondition] = useState(contract.stop_conditions[0]?.condition ?? "");
  const [evidence, setEvidence] = useState(contract.required_real_world_evidence.join("\n"));
  const [reviewed, setReviewed] = useState(contract.prohibited_outcomes_reviewed);
  const [result, setResult] = useState<RevisionWriteResult | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => titleRef.current?.focus(), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next = await onSave({
      targetSegments: splitPeople(targetSegments), applicableContexts: splitLines(contexts),
      targetOutcome: targetOutcome.trim(), indicatorDefinition: indicatorDefinition.trim(),
      observationMethod: observationMethod.trim(), thresholdOrTarget: threshold.trim(),
      prohibitedOutcomes: splitLines(prohibited), timeBudget: timeBudget.trim(),
      dataBoundary: dataBoundary.trim(), stopCondition: stopCondition.trim(),
      requiredRealWorldEvidence: splitLines(evidence), prohibitedOutcomesReviewed: reviewed,
    });
    setResult(next);
    if (next.status === "saved") onCancel();
  }
  const valid = Boolean(
    splitPeople(targetSegments).length && splitLines(contexts).length && targetOutcome.trim() &&
    indicatorDefinition.trim() && observationMethod.trim() && threshold.trim() &&
    stopCondition.trim() && splitLines(evidence).length,
  );
  return (
    <form className="intent-editor" onSubmit={(event) => void submit(event)}>
      <header><div><p className="eyebrow">Human value boundary</p><h3 ref={titleRef} tabIndex={-1}>纠正结果契约</h3><p>fake provider 只搭建结构。成功阈值、禁止结果和现实证据必须由人复核。</p></div><span className="revision">基于 r{contract.meta.revision}</span></header>
      <div className="intent-editor__grid">
        <label>目标人群<input value={targetSegments} onChange={(event) => setTargetSegments(event.target.value)} /></label>
        <label>适用情境<textarea rows={3} value={contexts} onChange={(event) => setContexts(event.target.value)} /></label>
        <label className="intent-editor__wide">目标结果<textarea rows={3} value={targetOutcome} onChange={(event) => setTargetOutcome(event.target.value)} /></label>
        <label>可观察指标<textarea rows={4} value={indicatorDefinition} onChange={(event) => setIndicatorDefinition(event.target.value)} /></label>
        <label>观察方法<textarea rows={4} value={observationMethod} onChange={(event) => setObservationMethod(event.target.value)} /></label>
        <label className="intent-editor__wide">成功阈值<input value={threshold} onChange={(event) => setThreshold(event.target.value)} /></label>
        <label>禁止结果<textarea rows={4} value={prohibited} onChange={(event) => setProhibited(event.target.value)} /><small>每行一项；可以为空，但仍须明确完成审查</small></label>
        <label>停止/重新定义条件<textarea rows={4} value={stopCondition} onChange={(event) => setStopCondition(event.target.value)} /></label>
        <label>时间边界<input value={timeBudget} onChange={(event) => setTimeBudget(event.target.value)} /></label>
        <label>数据边界<input value={dataBoundary} onChange={(event) => setDataBoundary(event.target.value)} /></label>
        <label className="intent-editor__wide">必须获得的现实证据<textarea rows={3} value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
        <label className="review-checkbox intent-editor__wide"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} /><span>我已审查禁止结果与伤害边界；这不是由 fake provider 自动批准的。</span></label>
      </div>
      <ResultMessage result={result} />
      <footer><span>未勾选审查仍可保存，但领域 Gate 不允许确认</span><div><button className="button button--quiet" onClick={onCancel} disabled={busy} type="button">取消</button><button className="button button--primary" disabled={busy || !valid}>保存结果契约提案</button></div></footer>
    </form>
  );
}
