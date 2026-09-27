import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function expectNoSeriousAccessibilityViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (violation) => violation.impact === "critical" || violation.impact === "serious",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
}

test("onboarding, intent correction, conflict recovery and confirmation", async ({ page }) => {
  const suffix = Date.now().toString(36);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "你不需要先把 产品想完整。" })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByLabel("项目名称").fill(`专注边界 ${suffix}`);
  await page.getByLabel("用一句不完整的话描述你想改变的现实").fill("减少不必要的工作打断");
  await page.getByRole("button", { name: /建立产品工作空间/ }).click();

  await expect(page).toHaveURL(/\/projects\/project-/);
  await expect(page.getByRole("heading", { name: "减少不必要的工作打断" })).toBeVisible();
  const projectId = decodeURIComponent(new URL(page.url()).pathname.split("/").pop()!);

  const editButton = page.getByRole("button", { name: "纠正产品意图" });
  await editButton.focus();
  await page.keyboard.press("Enter");
  const editorTitle = page.getByRole("heading", { name: "纠正产品意图" });
  await expect(editorTitle).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(editorTitle).toBeHidden();
  await expect(editButton).toBeFocused();

  await editButton.click();
  const desiredChange = page.getByLabel("希望什么发生改变？");
  await desiredChange.fill("减少打断，同时保留紧急联系");
  await page.getByLabel("受到影响的人").fill("独立工作者");
  await page.getByLabel("当前情境").fill("多个工具持续产生消息");
  await page.getByLabel("明确不做什么").fill("监控个人生产力\n阻断紧急消息");
  await page.getByLabel("已知约束").fill("本地优先");
  await page.getByLabel("资源倾向").fill("一天内获得可用原型");
  await expectNoSeriousAccessibilityViolations(page);

  const viewResponse = await page.request.get(`/api/v1/projects/${projectId}`);
  expect(viewResponse.ok()).toBeTruthy();
  const view = await viewResponse.json();
  const currentIntent = view.product_intent;
  const competingWrite = await page.request.post(
    `/api/v1/projects/${projectId}/product-intent/proposals`,
    {
      data: {
        proposal: {
          desired_change: currentIntent.desired_change,
          affected_people: currentIntent.affected_people,
          current_situation: currentIntent.current_situation,
          explicit_non_goals: currentIntent.explicit_non_goals,
          known_constraints: ["另一个客户端新增的约束"],
          resource_preferences: currentIntent.resource_preferences,
          source_refs: [
            ...currentIntent.source_refs,
            { source_type: "user_input", source_id: `competing-${suffix}` },
          ],
        },
        intent_id: currentIntent.intent_id,
        expected_revision: currentIntent.meta.revision,
        actor: "other-local-user",
        reason: "Simulate a concurrent correction",
      },
    },
  );
  expect(competingWrite.status()).toBe(201);

  await page.getByRole("button", { name: "保存为新提案" }).click();
  await expect(page.getByRole("alert")).toContainText("已刷新到 r2");
  await expect(desiredChange).toHaveValue("减少打断，同时保留紧急联系");
  await expect(page.getByText("基于服务端 r2")).toBeVisible();

  await page.getByRole("button", { name: "保存为新提案" }).click();
  await expect(editorTitle).toBeHidden();
  await expect(page.getByRole("heading", { name: "减少打断，同时保留紧急联系" })).toBeVisible();
  await expect(page.getByText("r3")).toBeVisible();

  await page.getByRole("button", { name: /决策与待办/ }).click();
  await page.getByRole("button", { name: "确认产品意图" }).click();
  await expect(page.getByRole("heading", { name: "现在不需要你做决定" })).toBeVisible();

  await page.getByRole("button", { name: /产品契约/ }).click();
  await expect(page.getByText("已确认", { exact: true })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});

test("fake provider jobs form a human-confirmed Product Contract", async ({ page }) => {
  const suffix = Date.now().toString(36);
  await page.goto("/");
  await page.getByLabel("项目名称").fill(`契约闭环 ${suffix}`);
  await page.getByLabel("用一句不完整的话描述你想改变的现实").fill("让独立工作者在专注时少被无关消息打断");
  await page.getByRole("button", { name: /建立产品工作空间/ }).click();

  await page.getByRole("button", { name: "纠正产品意图" }).click();
  await page.getByLabel("受到影响的人").fill("独立工作者");
  await page.getByLabel("当前情境").fill("桌面工作时多个工具持续产生消息");
  await page.getByRole("button", { name: "保存为新提案" }).click();
  await page.getByRole("button", { name: /决策与待办/ }).click();
  await page.getByRole("button", { name: "确认产品意图" }).click();
  await page.getByRole("button", { name: /产品契约/ }).click();

  await page.getByRole("button", { name: "生成问题模型提案" }).click();
  await expect(page.getByRole("heading", { name: "问题模型等待人类纠正与确认" })).toBeVisible();
  await expect(page.getByText("提案已生成", { exact: true })).toBeVisible();
  await expect(page.getByText(/fake provider 验证 proposal\/confirm/)).toBeVisible();
  await page.getByRole("button", { name: "纠正问题模型" }).click();
  const explanations = page.getByLabel("竞争性解释");
  await explanations.fill(
    "无关通知的到达时机造成非自愿切换\n任务边界不清导致主动查看消息",
  );
  await page.getByRole("button", { name: "保存问题提案" }).click();
  await expect(page.getByText("r2", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /决策与待办/ }).click();
  await page.getByRole("button", { name: "确认当前问题模型" }).click();
  await page.getByRole("button", { name: /产品契约/ }).click();
  await page.getByRole("button", { name: "生成结果契约提案" }).click();
  await expect(page.getByRole("heading", { name: "结果契约等待价值边界审查" })).toBeVisible();

  await page.getByRole("button", { name: /决策与待办/ }).click();
  await page.getByRole("button", { name: "确认结果契约" }).click();
  await expect(page.getByRole("alert")).toContainText("领域契约");

  await page.getByRole("button", { name: /产品契约/ }).click();
  await page.getByRole("button", { name: "纠正结果契约" }).click();
  await page.getByLabel("成功阈值").fill("相比无辅助基线，非计划任务切换更少");
  await page.getByLabel(/我已审查禁止结果与伤害边界/).check();
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("button", { name: "保存结果契约提案" }).click();

  await page.getByRole("button", { name: /决策与待办/ }).click();
  await page.getByRole("button", { name: "确认结果契约" }).click();
  await expect(page.getByRole("heading", { name: "现在不需要你做决定" })).toBeVisible();
  await page.getByRole("button", { name: /产品契约/ }).click();
  await expect(page.getByRole("heading", { name: "Product Contract 已形成" })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("button", { name: /产品工作台/ }).click();
  await expect(page.getByRole("heading", { name: "先比较几条真正不同的产品路径" })).toBeVisible();
  await page.getByRole("button", { name: "生成 3 条产品论点" }).click();
  await expect(page.getByRole("heading", { name: "产品论点与实现分支" })).toBeVisible();
  await expect(page.getByText("3 条路径", { exact: true })).toBeVisible();
  await expect(page.getByText("Urgency-aware interruption gate", { exact: true })).toBeVisible();
  await expect(page.getByText("Deliberate contact checkpoints", { exact: true })).toBeVisible();
  await expect(page.getByText("Re-entry bookmark", { exact: true })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("button", { name: /决策与待办/ }).click();
  await expect(page.getByText("3 项待办", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "授权低成本探索" })).toHaveCount(3);
  await expect(page.getByRole("button", { name: "选择此论点" })).toHaveCount(3);
  await page.getByRole("button", { name: "授权低成本探索" }).first().click();
  await page.getByRole("button", { name: "选择此论点" }).nth(1).click();
  await page.getByRole("button", { name: /产品工作台/ }).click();
  await expect(page.getByText("探索中", { exact: true })).toBeVisible();
  await expect(page.getByText("已选择", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /证据与进度/ }).click();
  await page.getByRole("button", { name: "生成测量计划" }).click();
  await expect(page.getByRole("heading", { name: "怎样观察结果，而不把解释冒充证据" })).toBeVisible();
  await expect(page.getByText("研究观察")).toBeVisible();
  await expect(page.getByText("用户报告")).toBeVisible();
  await page.getByRole("button", { name: "修改阈值" }).click();
  const threshold = page.getByRole("textbox", { name: "Observed in a consented task session threshold" });
  await threshold.fill("每位参与者非计划切换次数低于个人无辅助基线");
  await page.getByRole("button", { name: "保存阈值" }).click();
  await expect(page.getByText("每位参与者非计划切换次数低于个人无辅助基线")).toBeVisible();
  await page.getByRole("button", { name: "确认测量计划" }).click();
  await expect(page.getByText("已确认", { exact: true })).toBeVisible();
  await expect(page.getByText("尚未执行真实试用")).toBeVisible();
  await expect(page.getByRole("heading", { name: "只在明确同意后记录一条人工观察" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始本地 C1 试用" })).toBeDisabled();
  await expectNoSeriousAccessibilityViolations(page);
});


test("workspace recovery resumes a queued proposal job", async ({ page }) => {
  const suffix = Date.now().toString(36);
  const projectResponse = await page.request.post("/api/v1/projects", {
    data: {
      name: `可恢复工作区 ${suffix}`,
      collaboration_mode: "managed",
      actor: "e2e-user",
      reason: "create recovery fixture",
      created_from: [],
    },
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json();
  const jobResponse = await page.request.post(`/api/v1/projects/${project.project_id}/proposal-jobs`, {
    data: {
      kind: "product_intent",
      raw_input: "恢复后继续处理专注工作中的无关打断",
      provider: "deterministic_fake",
      actor: "e2e-user",
      reason: "queue recovery fixture",
    },
  });
  expect(jobResponse.status()).toBe(202);

  await page.goto("/");
  const projectButton = page.getByRole("button", { name: new RegExp(`可恢复工作区 ${suffix}`) });
  await expect(projectButton).toBeVisible();
  await projectButton.click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project.project_id}`));
  await expect(page.getByText("发现未完成工作", { exact: true })).toBeVisible();
  await expect(page.getByText(/提案 Job（product_intent）/)).toBeVisible();

  await page.getByRole("button", { name: "继续这项工作" }).click();
  await expect(page.getByRole("heading", { name: "恢复后继续处理专注工作中的无关打断" })).toBeVisible();
  await expect(page.getByText("发现未完成工作", { exact: true })).toBeHidden();
});
