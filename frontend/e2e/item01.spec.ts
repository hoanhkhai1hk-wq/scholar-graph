import { test, expect } from "@playwright/test";
import path from "node:path";

const v1 = "paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476";
// Real isolated service and official files. No route/model mocks in these tests.
test("第1项：真实网页修改、回收站和恢复", async ({ page, request }) => {
  const original = (await (await request.get(`/api/workspace/papers/${v1}`)).json()).paper.title;
  const card = page.locator("article.sg-paper-card").filter({ has: page.locator(`a[href="/read/${v1}"]`) });
  try {
    await page.goto("/"); await card.getByRole("button", { name: "编辑信息" }).click();
    await page.getByRole("dialog").getByLabel("标题", { exact: true }).fill(original + "（网页验收）");
    await page.getByRole("button", { name: "保存修正", exact: true }).click();
    await expect(card.getByRole("heading")).toContainText("（网页验收）");
    await card.getByRole("button", { name: "编辑信息" }).click();
    await page.getByRole("dialog").getByLabel("标题", { exact: true }).fill(original);
    await page.getByRole("button", { name: "保存修正", exact: true }).click();
    await expect(card.getByRole("heading")).toHaveText(original);
    await card.getByRole("button", { name: "移入回收站", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "移入回收站", exact: true }).click();
    await expect(card).toHaveCount(0); await page.getByRole("button", { name: "回收站", exact: true }).click();
    await card.getByRole("button", { name: "恢复论文", exact: true }).click(); await expect(card).toHaveCount(0);
    await page.getByRole("button", { name: "返回论文库", exact: true }).click(); await expect(card).toBeVisible();
  } finally {
    await request.patch(`/api/workspace/papers/${v1}`, { data: { title: original } });
    await request.post(`/api/workspace/papers/${v1}/restore`);
  }
});

test("第1项：官方文件批量上传网页入口（已入库缓存）", async ({ page, request }, info) => {
  await page.goto("/upload");
  await page.locator('input[type="file"]').setInputFiles([
    path.resolve("../pdf/1607.06450v1.pdf"), path.resolve("../pdf/N19-1423.pdf")]);
  await page.getByRole("button", { name: "上传并解析 2 篇", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("link", { name: "打开论文", exact: true })).toHaveCount(2);
  await expect(page.locator(".sg-error")).toHaveCount(0);
  const id = await page.evaluate(() => localStorage.getItem("sg.upload.task"));
  const result = await (await request.get(`/api/workspace/tasks/${id}`)).json();
  expect(result.status).toBe("completed"); expect(result.result.succeeded_count).toBe(2); expect(result.result.failed_count).toBe(0);
  await page.screenshot({ path: info.outputPath("batch-cache-completed.png") });
});

test("第1项：表格真实单元格、作者顺序与公式修正入口", async ({ page }, info) => {
  await page.goto(`/read/${v1}`); await page.getByRole("tab", { name: "信息与解析", exact: true }).click();
  await expect(page.getByRole("heading", { name: "作者与对应机构、联系方式" })).toBeVisible();
  const authors = page.locator("table").first().locator("tbody tr"); await expect(authors).toHaveCount(8);
  await expect(authors.first()).toContainText("Ashish Vaswani"); await expect(authors.last()).toContainText("Illia Polosukhin");
  await page.getByLabel("内容类型", { exact: true }).selectOption("table");
  await expect(page.locator("article table")).toHaveCount(4);
  expect(await page.locator("article table").evaluateAll(tables => tables.map(t => t.querySelectorAll("td,th").length))).toEqual([20,57,102,36]);
  expect(await page.locator("main").innerText()).not.toContain("<table>");
  await page.locator("article.sg-structure-item").first().screenshot({ path: info.outputPath("table-cells.png") });
  await expect(page.getByRole("heading", { name: "公式 LaTeX 与原图核对" })).toBeVisible();
});
