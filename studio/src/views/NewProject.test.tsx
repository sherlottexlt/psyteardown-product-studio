import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createProject, createProposalJob, listProjects, runProposalJob } from "../api/client";
import { NewProject } from "./NewProject";

vi.mock("../api/client", () => ({
  createProject: vi.fn(),
  createProposalJob: vi.fn(),
  listProjects: vi.fn(),
  runProposalJob: vi.fn(),
}));

describe("NewProject", () => {
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
});
