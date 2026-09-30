import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createProject, createProposalJob, listProjects, runProposalJob } from "../api/client";
import { NewProject } from "./NewProject";

vi.mock("../api/client", () => ({
  createProject: vi.fn(),
  createProposalJob: vi.fn(),
  listProjects: vi.fn(),
  runProposalJob: vi.fn(),
}));

describe("NewProject", () => {
  afterEach(() => cleanup());
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(listProjects).mockResolvedValue([]); });

  it("persists raw input through a proposal job before opening the project", async () => {
    const createProjectMock = vi.mocked(createProject);
    const createProposalJobMock = vi.mocked(createProposalJob);
    const runProposalJobMock = vi.mocked(runProposalJob);
    createProjectMock.mockResolvedValue({ project_id: "project-1" } as never);
    createProposalJobMock.mockResolvedValue({ job_id: "job-1", status: "queued" } as never);
    runProposalJobMock.mockResolvedValue({ job_id: "job-1", status: "succeeded" } as never);
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<NewProject lastProjectId={null} onCreated={onCreated} />);

    await user.type(screen.getByLabelText("项目名称"), "保护专注");
    await user.type(
      screen.getByLabelText("用一句不完整的话描述你想改变的现实"),
      "减少不必要的工作打断",
    );
    await user.click(screen.getByRole("button", { name: /建立产品工作空间/ }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("project-1"));
    expect(createProject).toHaveBeenCalledWith({
      name: "保护专注",
      collaborationMode: "managed",
    });
    expect(createProposalJob).toHaveBeenCalledWith({
      projectId: "project-1",
      kind: "product_intent",
      rawInput: "减少不必要的工作打断",
      provider: "deterministic_fake",
    });
    expect(runProposalJob).toHaveBeenCalledWith({
      projectId: "project-1",
      jobId: "job-1",
    });
    expect(createProjectMock.mock.invocationCallOrder[0]!).toBeLessThan(
      createProposalJobMock.mock.invocationCallOrder[0]!,
    );
  });

  it("lets the first proposal explicitly use the real provider", async () => {
    vi.mocked(createProject).mockResolvedValue({ project_id: "project-real" } as never);
    vi.mocked(createProposalJob).mockResolvedValue({ job_id: "job-real", status: "queued" } as never);
    vi.mocked(runProposalJob).mockResolvedValue({ job_id: "job-real", status: "succeeded" } as never);
    const user = userEvent.setup();
    render(<NewProject lastProjectId={null} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("项目名称"), "本地对比板");
    await user.type(screen.getByLabelText("用一句不完整的话描述你想改变的现实"), "我希望比较两个选择时更快看出差异");
    await user.selectOptions(screen.getByLabelText("首次提案 provider"), "real");
    await user.click(screen.getByRole("button", { name: /建立产品工作空间/ }));

    await waitFor(() => expect(createProposalJob).toHaveBeenCalledWith({
      projectId: "project-real",
      kind: "product_intent",
      rawInput: "我希望比较两个选择时更快看出差异",
      provider: "real",
    }));
  });

});
