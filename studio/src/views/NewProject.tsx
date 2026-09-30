import { type FormEvent, useEffect, useState } from "react";
import {
  changeProjectStatus,
  createProject,
  createProposalJob,
  listProjects,
  runProposalJob,
} from "../api/client";
import type { CollaborationMode, ProductProject } from "../api/types";
import { formatApiError } from "../domain/project";

type ProposalProvider = "deterministic_fake" | "real";

export function NewProject({
  onCreated,
  lastProjectId,
}: {
  onCreated: (projectId: string) => void;
  lastProjectId: string | null;
}) {
  const [name, setName] = useState("");
  const [desiredChange, setDesiredChange] = useState("");
  const [mode, setMode] = useState<CollaborationMode>("managed");
  const [proposalProvider, setProposalProvider] = useState<ProposalProvider>("deterministic_fake");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [projects, setProjects] = useState<ProductProject[]>([]);
  const [updatingProjectId, setUpdatingProjectId] = useState<string | null>(null);

  async function refreshProjects() {
    const values = await listProjects();
    setProjects(values);
  }

  useEffect(() => {
    let active = true;
    void listProjects()
      .then((values) => { if (active) setProjects(values); })
      .catch(() => { /* the new-project form remains usable when recovery is unavailable */ });
    return () => { active = false; };
  }, []);

  async function handleProjectStatus(project: ProductProject, toStatus: "active" | "archived") {
    if (toStatus === "archived" && !window.confirm(`归档“${project.name}”？它会从最近项目中隐藏，但不会删除数据或历史。`)) return;
    setUpdatingProjectId(project.project_id);
    setError(null);
    try {
      await changeProjectStatus({
        projectId: project.project_id,
        expectedRevision: project.meta.revision,
        toStatus,
        reason: toStatus === "archived" ? "Hide an abandoned local project from the recovery list" : "Restore an archived local project",
      });
      await refreshProjects();
    } catch (cause) {
      setError(formatApiError(cause));
    } finally {
      setUpdatingProjectId(null);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !desiredChange.trim()) return;
    setSubmitting(true);
    setError(null);
    let createdProjectId: string | null = null;
    try {
      const project = await createProject({ name: name.trim(), collaborationMode: mode });
      createdProjectId = project.project_id;
      const queued = await createProposalJob({
        projectId: project.project_id,
        kind: "product_intent",
        rawInput: desiredChange.trim(),
        provider: proposalProvider,
      });
      const completed = await runProposalJob({
        projectId: project.project_id,
        jobId: queued.job_id,
      });
      if (completed.status !== "succeeded") {
        throw new Error(
          completed.error_summary ?? "初始意图提案没有成功生成，请从已创建的项目继续。",
        );
      }
      onCreated(project.project_id);
    } catch (cause) {
      setError(
        createdProjectId
          ? `${formatApiError(cause)} 项目已经创建，可从 ${createdProjectId} 继续。`
          : formatApiError(cause),
      );
    } finally {
      setSubmitting(false);
    }
  }

  const valid = Boolean(name.trim() && desiredChange.trim() && desiredChange.trim().length <= 4000);
  const activeProjects = projects.filter((project) => project.status !== "archived");
  const archivedProjects = projects.filter((project) => project.status === "archived");

  return (
    <main className="landing-shell">
      <header className="landing-nav">
        <a className="brand" href="/" aria-label="psyteardown Product Studio">
          <span className="brand__signal" aria-hidden="true"><i /><i /><i /></span>
          <span>psyteardown</span>
        </a>
        <span className="landing-nav__label">AI Product Studio · local preview</span>
      </header>

      <div className="landing-grid">
        <section className="landing-story">
          <p className="eyebrow">从值得改变的现实开始</p>
          <h1>你不需要先把<br />产品想完整。</h1>
          <p className="landing-story__lead">
            告诉我们你希望什么发生改变。工作室会把模糊意图发展成可纠正的契约、可证伪的路径和可运行的产品。
          </p>
          <div className="principle-list" aria-label="工作方式">
            <div><span>01</span><p><strong>理解先于生成</strong>先确认目标、情境与不可接受的结果。</p></div>
            <div><span>02</span><p><strong>成果先于报告</strong>优先让你直接使用，而不是阅读产品描述。</p></div>
            <div><span>03</span><p><strong>证据先于声称</strong>未知、风险和适用边界始终可见。</p></div>
          </div>
          <div className="recovery-banner" role="note">
            <div><strong>现在开始的是原型工作，不是正式自试。</strong><small>建立项目、预览原型、记录真实任务观察是三个不同阶段；C1 真实观察仍需单独满足门槛。</small></div>
          </div>
        </section>

        <section className="start-card" aria-labelledby="start-title">
          <div className="start-card__header">
            <p className="eyebrow">新建产品计划</p>
            <h2 id="start-title">先说说，你想改变什么？</h2>
            <p>不必写 PRD。一段真实、不完整的描述就够了。</p>
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              项目名称
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：少被打断的专注工作"
                autoFocus
              />
            </label>
            <label htmlFor="desired-change">用一句不完整的话描述你想改变的现实</label>
            <textarea
              id="desired-change"
              value={desiredChange}
              onChange={(event) => setDesiredChange(event.target.value.slice(0, 4000))}
              placeholder="我希望独立工作时，不再被无关消息不断打断……"
              rows={4}
              maxLength={4000}
              aria-describedby="desired-change-help"
            />
            <small id="desired-change-help" className="field-hint">{desiredChange.length}/4000 · 原始输入会保存在本地，并发送给你选择的提案 provider。</small>
            <label htmlFor="proposal-provider">首次提案 provider</label>
            <select id="proposal-provider" value={proposalProvider} onChange={(event) => setProposalProvider(event.target.value as ProposalProvider)}>
              <option value="deterministic_fake">fake（离线、合成内容）</option>
              <option value="real">real（DeepSeek，需要外发输入）</option>
            </select>
            <small className="field-hint">
              {proposalProvider === "real"
                ? "会把原始输入发送给已配置的 DeepSeek；输出仍需你审阅，不是事实或证据。"
                : "不会联网；输出是为了走通工作流的合成提案，不代表研究结论。"}
            </small>
            <label htmlFor="collaboration-mode">协作方式</label>
            <select id="collaboration-mode" value={mode} onChange={(event) => setMode(event.target.value as CollaborationMode)} aria-describedby="collaboration-help">
              <option value="managed">托管模式</option>
              <option value="co_design">共同设计</option>
              <option value="governance">治理模式</option>
            </select>
            <small id="collaboration-help" className="field-hint">当前版本只记录你的协作偏好，不改变权限、提案流程或数据治理；个人探索可先用“托管模式”。</small>
            {error ? <p className="form-error" role="alert">{error}</p> : null}
            <button className="button button--primary button--wide" disabled={!valid || submitting}>
              {submitting ? `正在保存原始输入并形成${proposalProvider === "real" ? "真实 provider" : "离线"}提案…` : "建立产品工作空间"}
              <span aria-hidden="true">↗</span>
            </button>
          </form>
          {activeProjects.length ? (
            <section className="recent-projects" aria-label="最近的产品工作空间">
              <div className="recent-projects__heading"><span className="eyebrow">Recent workspaces</span><small>项目保存在本地，可恢复未完成工作；归档只隐藏，不等于删除。</small></div>
              <ul>
                {activeProjects.slice(0, 6).map((project: ProductProject) => (
                  <li key={project.project_id}>
                    <div className="recent-project-row">
                      <button type="button" onClick={() => onCreated(project.project_id)}>
                        <strong>{project.name}</strong><small>{project.project_id} · {project.status === "active" ? "进行中" : "已暂停"}</small>
                      </button>
                      <button className="text-button recent-project-action" type="button" disabled={updatingProjectId === project.project_id} onClick={() => void handleProjectStatus(project, "archived")}>
                        {updatingProjectId === project.project_id ? "处理中…" : "归档"}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {archivedProjects.length ? (
            <section className="recent-projects recent-projects--archived" aria-label="已归档的产品工作空间">
              <div className="recent-projects__heading"><span className="eyebrow">Archived</span><small>归档不会删除 SQLite 历史、workspace 或导出物。</small></div>
              <ul>
                {archivedProjects.slice(0, 6).map((project: ProductProject) => (
                  <li key={project.project_id}>
                    <div className="recent-project-row">
                      <button type="button" onClick={() => onCreated(project.project_id)}>
                        <strong>{project.name}</strong><small>{project.project_id} · 已归档</small>
                      </button>
                      <button className="text-button recent-project-action" type="button" disabled={updatingProjectId === project.project_id} onClick={() => void handleProjectStatus(project, "active")}>
                        {updatingProjectId === project.project_id ? "处理中…" : "恢复"}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {!activeProjects.length && !archivedProjects.length && lastProjectId ? (
            <button className="text-button" onClick={() => onCreated(lastProjectId)} type="button">
              继续上次项目 <span>{lastProjectId}</span>
            </button>
          ) : null}
        </section>
      </div>
    </main>
  );
}
