import { useQuery } from "@tanstack/react-query";
import {
  enrollC1Participant,
  endC1Envelope,
  getC1Policy,
  listC1Envelopes,
  listC1Observations,
  listC1Participants,
  listC1Reviews,
  presentC1Task,
  recordC1Observation,
  reviewC1Evidence,
  startC1Envelope,
  withdrawC1Participant,
} from "../api/client";
import type { OutcomeMeasurementPlan, ProductDeliveryBundle, ProductExecutionJob, ProductProjectView } from "../api/types";
import { useState } from "react";
import { Badge } from "../components/Badge";

type C1ObservationStatus =
  | "observed"
  | "participant_withdrawal"
  | "task_abandonment"
  | "technical_failure"
  | "skipped_by_protocol"
  | "no_response"
  | "not_applicable"
  | "unknown";

type C1ReviewDecision = "accepted" | "modified" | "rejected" | "insufficient";
type C1EvidenceLevel = "none" | "exploratory" | "observed";

function parseObservationValue(raw: string): string | number | boolean {
  if (raw === "true") return true;
  if (raw === "false") return false;
  const number = Number(raw);
  return raw.trim() !== "" && !Number.isNaN(number) ? number : raw;
}

export function C1Panel({
  projectId,
  view,
  plan,
  deliveryBundle,
  executionJob,
  busy = false,
  onChanged,
  onError,
}: {
  projectId: string;
  view: ProductProjectView;
  plan: OutcomeMeasurementPlan;
  deliveryBundle: ProductDeliveryBundle | null;
  executionJob: ProductExecutionJob | null;
  busy?: boolean;
  onChanged: () => Promise<unknown>;
  onError: (message: string) => void;
}) {
  const policyQuery = useQuery({ queryKey: ["c1-policy"], queryFn: getC1Policy, retry: false });
  const envelopesQuery = useQuery({ queryKey: ["c1-envelopes", projectId], queryFn: () => listC1Envelopes(projectId), retry: false });
  const envelope = (envelopesQuery.data ?? []).at(-1) ?? null;
  const participantsQuery = useQuery({
    queryKey: ["c1-participants", projectId, envelope?.envelope_id],
    queryFn: () => listC1Participants(projectId, envelope!.envelope_id),
    enabled: Boolean(envelope),
    retry: false,
  });
  const observationsQuery = useQuery({
    queryKey: ["c1-observations", projectId, envelope?.envelope_id],
    queryFn: () => listC1Observations(projectId, envelope!.envelope_id),
    enabled: Boolean(envelope),
    retry: false,
  });
  const reviewsQuery = useQuery({
    queryKey: ["c1-reviews", projectId, envelope?.envelope_id],
    queryFn: () => listC1Reviews(projectId, envelope!.envelope_id),
    enabled: Boolean(envelope),
    retry: false,
  });

  const [participantId, setParticipantId] = useState("");
  const [presentationId, setPresentationId] = useState("");
  const [taskId, setTaskId] = useState(view.web_generation_contract?.tasks[0]?.task_id ?? "");
  const [measureId, setMeasureId] = useState(plan.measures.find((item) => item.source_layer === "research_observation")?.measure_id ?? "");
  const [value, setValue] = useState("true");
  const [status, setStatus] = useState<C1ObservationStatus>("observed");
  const [completionCause, setCompletionCause] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [reviewObservationId, setReviewObservationId] = useState("");
  const [reviewDecision, setReviewDecision] = useState<C1ReviewDecision>("accepted");
  const [reviewLevel, setReviewLevel] = useState<C1EvidenceLevel>("observed");
  const [reviewRationale, setReviewRationale] = useState("Reviewed the structured task record");
  const [consentChecked, setConsentChecked] = useState(false);
  const [endReason, setEndReason] = useState("");

  const policy = policyQuery.data;
  const participants = participantsQuery.data ?? [];
  const activeParticipants = participants.filter((item) => item.status === "active");
  const currentParticipant = activeParticipants.find((item) => item.participant_id === participantId) ?? activeParticipants.at(-1) ?? null;
  const observations = observationsQuery.data ?? [];
  const reviews = reviewsQuery.data ?? [];
  const reviewedObservationIds = new Set(reviews.flatMap((item) => item.observation_ids));
  const reviewableObservations = observations.filter((item) => !reviewedObservationIds.has(item.observation_id));
  const selectedReviewObservationId = reviewableObservations.some((item) => item.observation_id === reviewObservationId)
    ? reviewObservationId
    : reviewableObservations.at(0)?.observation_id ?? "";
  const selectedReviewObservation = reviewableObservations.find((item) => item.observation_id === selectedReviewObservationId) ?? null;
  const reviewPromotionInvalid = selectedReviewObservation?.status !== "observed"
    && (reviewDecision === "accepted" || reviewDecision === "modified" || reviewLevel !== "none");
  const contract = view.web_generation_contract;
  const researchMeasures = plan.measures.filter((item) => item.source_layer === "research_observation");
  const reviewByObservationId = new Map(reviews.flatMap((review) => review.observation_ids.map((id) => [id, review] as const)));
  const queryError = [policyQuery.error, envelopesQuery.error, participantsQuery.error, observationsQuery.error, reviewsQuery.error]
    .find((error): error is Error => error instanceof Error);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      await Promise.all([
        envelopesQuery.refetch(),
        participantsQuery.refetch(),
        observationsQuery.refetch(),
        reviewsQuery.refetch(),
        onChanged(),
      ]);
    } catch (error) {
      onError(error instanceof Error ? error.message : "C1 操作失败，请检查后端状态。");
    }
  }

  const canStart = plan.status === "confirmed" && deliveryBundle?.contract_is_current && executionJob?.status === "succeeded" && Boolean(contract) && policy?.trial_state === "available";
  const completionCauseRequired = status !== "observed" && !completionCause.trim();
  const envelopeActive = envelope?.status === "active";
  return (
    <section className="panel evidence-section evidence-section--wide c1-panel" aria-labelledby="c1-panel-title">
      <div className="panel__heading">
        <div><p className="eyebrow">C1 · Local task observation</p><h2 id="c1-panel-title">只在明确同意后记录一条人工观察</h2></div>
        <Badge tone={envelope?.status === "active" ? "warn" : "good"}>{envelope ? envelope.status : "未开始"}</Badge>
      </div>
      <p className="measurement-plan-intro">本地主持、随机参与者 ID、结构化 measure 和具名 reviewer。不会采集屏幕、键鼠、通知、遥测或参与者原始文本；C1 只接受 research_observation，证据上限为 observed。</p>
      {queryError ? <p className="action-error" role="alert">C1 数据读取失败：{queryError.message}</p> : null}
      {policy ? <div className="c1-policy"><strong>{policy.consent_policy_revision} · {policy.trial_state === "paused" ? "当前暂缓" : "可启动"}</strong><span>{policy.trial_status_message}</span><span>{policy.statement}</span><small>访问：{policy.access_policy.join("、")} · 保留：{policy.retention_policy}</small></div> : null}
      {!envelope ? (
        <div className="c1-actions">
          <button className="button button--primary" disabled={busy || !canStart} onClick={() => deliveryBundle && executionJob && void run(() => startC1Envelope({ projectId, measurementPlanRevisionId: plan.revision_id, deliveryBundleId: deliveryBundle.bundle_id, executionJobRevisionId: deliveryBundle.execution_job_revision_id, webGenerationContractRevisionId: deliveryBundle.web_generation_contract_revision_id }))}>开始本地 C1 试用</button>
          {!canStart ? <span className="unknown-copy">{policy?.trial_state === "paused" ? policy.trial_status_message : "需要确认的 C2 计划、当前 Web 契约和成功的 B6 交付包。"}</span> : null}
        </div>
      ) : !envelopeActive ? (
        <div className="c1-stack">
          <p className="c1-muted">该 trial 已{envelope?.status === "closed" ? "结束" : "停止"}；关闭后不再允许 enrollment、presentation 或 observation。源记录将在关闭后 30 天到期清理。</p>
          {envelope?.closed_at ? <small>关闭时间：{envelope.closed_at} · retention 到期：{envelope.retention_expires_at}</small> : null}
        </div>
      ) : (
        <div className="c1-stack">
          <div className="c1-grid">
            <div>
              <h3>1 · 参与者同意</h3>
              <label className="checkbox-label"><input type="checkbox" checked={consentChecked} onChange={(event) => setConsentChecked(event.target.checked)} />我已向参与者展示上方完整同意说明，并获得明确授权。</label>
              <button className="button button--quiet" disabled={busy || !consentChecked || !policy} onClick={() => void run(async () => { const result = await enrollC1Participant({ projectId, envelopeId: envelope.envelope_id, policyRevision: policy?.consent_policy_revision ?? "" }); setParticipantId(result.participant.participant_id); setPresentationId(""); setConsentChecked(false); })}>生成随机参与者 ID</button>
              {currentParticipant ? <code className="c1-participant-id">{currentParticipant.participant_id}</code> : null}
              {participants.some((item) => item.status === "withdrawn") ? <small className="c1-muted">已撤回参与者不会重新进入任务。</small> : null}
            </div>
            <div>
              <h3>2 · 主持任务</h3>
              <label>任务<select value={taskId} onChange={(event) => setTaskId(event.target.value)}>{(contract?.tasks ?? []).map((task) => <option value={task.task_id} key={task.task_id}>{task.task_id}</option>)}</select></label>
              <button className="button button--quiet" disabled={busy || !currentParticipant || !taskId} onClick={() => void run(async () => { const result = await presentC1Task({ projectId, envelopeId: envelope.envelope_id, participantId: currentParticipant!.participant_id, taskId }); setParticipantId(currentParticipant!.participant_id); setPresentationId(result.presentation_id); })}>开始任务 presentation</button>
              {presentationId ? <small>presentation：{presentationId}</small> : null}
            </div>
          </div>
          <div className="c1-grid">
            <div>
              <h3>3 · 结构化观察</h3>
              <label>measure<select value={measureId} onChange={(event) => setMeasureId(event.target.value)}>{researchMeasures.map((measure) => <option value={measure.measure_id} key={measure.measure_id}>{measure.label}</option>)}</select></label>
              <label>结果值<input value={value} onChange={(event) => setValue(event.target.value)} aria-label="C1 observation value" disabled={status !== "observed"} /></label>
              <label>状态<select value={status} onChange={(event) => setStatus(event.target.value as C1ObservationStatus)}><option value="observed">observed</option><option value="task_abandonment">task_abandonment</option><option value="technical_failure">technical_failure</option><option value="skipped_by_protocol">skipped_by_protocol</option><option value="no_response">no_response</option><option value="not_applicable">not_applicable</option><option value="unknown">unknown</option></select></label>
              <label>非成功原因（可复核）<input value={completionCause} onChange={(event) => setCompletionCause(event.target.value)} placeholder="例如：参与者主动退出" disabled={status === "observed"} /></label>
              <button className="button button--quiet" disabled={busy || !currentParticipant || !presentationId || !measureId || !researchMeasures.length || completionCauseRequired} onClick={() => void run(async () => { await recordC1Observation({ projectId, envelopeId: envelope.envelope_id, participantId: currentParticipant!.participant_id, presentationId, measureId, value: status === "observed" ? parseObservationValue(value) : null, completionCause: completionCause || undefined, status }); setCompletionCause(""); })}>保存观察</button>
            </div>
            <div>
              <h3>4 · 人工 EvidenceReview</h3>
              <label>待审观察<select aria-label="待审观察" value={selectedReviewObservationId} onChange={(event) => { const next = reviewableObservations.find((item) => item.observation_id === event.target.value); setReviewObservationId(event.target.value); if (next?.status !== "observed") { setReviewDecision("insufficient"); setReviewLevel("none"); } }} >{reviewableObservations.map((item) => <option value={item.observation_id} key={item.observation_id}>{item.measure_id} · {item.status} · {String(item.value ?? "—")}</option>)}</select></label>
              <label>reviewer（需与 host 分离）<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
              <label>判断<select value={reviewDecision} onChange={(event) => { const next = event.target.value as C1ReviewDecision; setReviewDecision(next); if (next === "rejected" || next === "insufficient") setReviewLevel("none"); }}><option value="accepted" disabled={selectedReviewObservation?.status !== "observed"}>accepted</option><option value="modified" disabled={selectedReviewObservation?.status !== "observed"}>modified</option><option value="rejected">rejected</option><option value="insufficient">insufficient</option></select></label>
              <label>等级<select value={reviewLevel} onChange={(event) => setReviewLevel(event.target.value as C1EvidenceLevel)}><option value="observed">observed</option><option value="exploratory">exploratory</option><option value="none">none</option></select></label>
              <label>理由<input value={reviewRationale} onChange={(event) => setReviewRationale(event.target.value)} /></label>
              <button className="button button--quiet" disabled={busy || !selectedReviewObservationId || !reviewer.trim() || !reviewRationale.trim() || reviewPromotionInvalid} onClick={() => void run(async () => { await reviewC1Evidence({ projectId, envelopeId: envelope.envelope_id, observationIds: [selectedReviewObservationId], reviewer, decision: reviewDecision, evidenceLevelAfter: reviewLevel, rationale: reviewRationale }); setReviewObservationId(""); })}>提交人工 review</button>
              {!reviewableObservations.length ? <small className="c1-muted">当前没有待审观察；每次 review 只提交一个 measure。</small> : null}
              {selectedReviewObservation?.status !== "observed" ? <small className="c1-muted">非成功路径只能以 rejected/insufficient 且等级 none 结束，不能升级为结果证据。</small> : null}
            </div>
          </div>
          {observations.length ? <div className="c1-observations"><h3>当前未撤回观察</h3>{observations.map((item) => { const review = reviewByObservationId.get(item.observation_id); return <div key={item.observation_id}><Badge tone={item.status === "observed" ? "good" : "warn"}>{item.status}</Badge><span>{item.measure_id} · {String(item.value ?? "—")}</span><small>{review ? `review: ${review.decision}/${review.evidence_level_after}` : "待人工 review"} · {item.recorded_at}</small></div>; })}</div> : null}
          {currentParticipant ? <button className="button button--quiet c1-withdraw" disabled={busy} onClick={() => void run(async () => { await withdrawC1Participant({ projectId, envelopeId: envelope.envelope_id, participantId: currentParticipant.participant_id }); setParticipantId(""); setPresentationId(""); })}>记录参与者撤回并擦除源记录</button> : null}
          <div className="c1-end-trial">
            <label>结束原因<input value={endReason} onChange={(event) => setEndReason(event.target.value)} placeholder="例如：本次本地试用完成" /></label>
            <div className="c1-actions">
              <button className="button button--quiet" disabled={busy || !endReason.trim()} onClick={() => void run(async () => { await endC1Envelope({ projectId, envelopeId: envelope.envelope_id, action: "close", reason: endReason.trim() }); setEndReason(""); })}>结束 trial</button>
              <button className="button button--quiet" disabled={busy || !endReason.trim()} onClick={() => void run(async () => { await endC1Envelope({ projectId, envelopeId: envelope.envelope_id, action: "stop", reason: endReason.trim() }); setEndReason(""); })}>停止 trial</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
