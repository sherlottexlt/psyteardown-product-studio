import { type FormEvent, useEffect, useState } from "react";
import { createProject, createProposalJob, listProjects, runProposalJob } from "../api/client";
import type { CollaborationMode, ProductProject } from "../api/types";
import { formatApiError } from "../domain/project";

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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [projects, setProjects] = useState<ProductProject[]>([]);
  useEffect(() => {
    let active = true;
    void listProjects().then((values) => { if (active) setProjects(values); }).catch(() => { /* the new-project form remains usable when recovery is unavailable */ });
    return () => { active = false; };
  }, []);

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
        provider: "deterministic_fake",
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
            <small id="desired-change-help" className="field-hint">{desiredChange.length}/4000 · 只在本地 Product Studio 保存并发送给所选 provider。</small>
            <label>
              协作方式
              <select value={mode} onChange={(event) => setMode(event.target.value as CollaborationMode)}>
                <option value="managed">托管模式</option>
                <option value="co_design">共同设计</option>
                <option value="governance">治理模式</option>
              </select>
            </label>
            {error ? <p className="form-error" role="alert">{error}</p> : null}
            <button className="button button--primary button--wide" disabled={!valid || submitting}>
              {submitting ? "正在保存原始输入并形成离线提案…" : "建立产品工作空间"}
              <span aria-hidden="true">↗</span>
            </button>
          </form>
          {projects.length ? (
            <section className="recent-projects" aria-label="最近的产品工作空间">
              <div className="recent-projects__heading"><span className="eyebrow">Recent workspaces</span><small>项目保存在本地，可随时恢复未完成工作。</small></div>
              <ul>
                {projects.slice(0, 6).map((project: ProductProject) => (
                  <li key={project.project_id}>
                    <button type="button" onClick={() => onCreated(project.project_id)}>
                      <strong>{project.name}</strong><small>{project.project_id} · {project.status === "active" ? "进行中" : project.status === "paused" ? "已暂停" : "已归档"}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : lastProjectId ? (
            <button className="text-button" onClick={() => onCreated(lastProjectId)} type="button">
              继续上次项目 <span>{lastProjectId}</span>
            </button>
          ) : null}
        </section>
      </div>
    </main>
  );
}
