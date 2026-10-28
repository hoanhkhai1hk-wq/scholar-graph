import { test, expect } from "@playwright/test";

const attention = "paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697";
const book = "paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32";
for (const [width, height] of [[1440, 900], [1366, 768], [1024, 768], [390, 844]]) {
  test(`导航、弹窗与正文 ${width}×${height}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "我的论文" })).toBeVisible();
    await expect(page.locator(".sg-paper-card").first()).toBeVisible();
    const nav = page.getByRole("complementary", { name: "主导航" });
    if (width < 768) {
      const trigger = page.getByRole("button", { name: "☰ 导航" });
      await trigger.click(); await expect(nav).toBeVisible();
      await expect(page.locator("#workspace-content")).toHaveAttribute("inert", "");
      await page.keyboard.press("Shift+Tab");
      expect(await page.locator("#main-navigation").evaluate(element => element.contains(document.activeElement))).toBeTruthy();
      await page.keyboard.press("Escape"); await expect(nav).not.toBeVisible(); await expect(trigger).toBeFocused();
    } else {
      const bounds = await nav.boundingBox(); expect(bounds?.x).toBe(16); expect(bounds?.y).toBe(16);
      expect(bounds?.width).toBe(width < 1280 ? 64 : 176);
      const content = await page.locator("#workspace-content").boundingBox(); expect(content!.x).toBeGreaterThan(bounds!.x + bounds!.width);
      await page.getByRole("button", { name: width < 1280 ? "展开导航" : "折叠导航", exact: true }).click();
      await expect(nav).toHaveClass(width < 1280 ? /sg-floating-nav(?!.*is-compact)/ : /is-compact/);
      const after = await nav.boundingBox(); expect(after?.width).toBe(width < 1280 ? 176 : 64);
    }
    const edit = page.locator(".sg-paper-card").first().getByRole("button", { name: /编辑/ });
    await edit.click(); await expect(page.getByRole("dialog")).toBeVisible();
    const dialog = await page.getByRole("dialog").boundingBox(); expect(dialog!.x).toBeGreaterThanOrEqual(0); expect(dialog!.x + dialog!.width).toBeLessThanOrEqual(width);
    await page.keyboard.press("Escape"); await expect(page.getByRole("dialog")).not.toBeVisible(); await expect(edit).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: info.outputPath(`library-${width}.png`) });
    await page.goto(`/read/${attention}`);
    await expect(page.getByRole("heading", { name: "Attention Is All You Need", exact: true })).toBeVisible();
    await expect(page.locator(".sg-pdfpage__stage canvas").first()).toBeVisible();
    await expect(page.locator('[data-page="1"]')).toHaveAttribute("data-rendered", "true");
    expect(await page.locator('[data-page="1"] canvas').evaluate(element => {
      const canvas = element as HTMLCanvasElement, data = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height).data;
      let dark = 0; for (let i = 0; i < data.length; i += 16) if (data[i] < 170 && data[i + 1] < 170 && data[i + 2] < 170 && data[i + 3] > 0) dark++;
      return dark;
    })).toBeGreaterThan(200);
    await expect(page.locator(".sg-layout__nav")).not.toContainText("@gmail.com");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: info.outputPath(`reader-${width}.png`) });
    expect(errors).toEqual([]);
  });
}

test("长书末页、分片请求与完整正文", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/read/${book}?page=541`);
  await expect(page.getByLabel("跳转页码")).toBeVisible();
  const pdf = await page.request.get(`/api/backend/papers/${book}/file`, { headers: { Range: "bytes=0-255" } });
  expect(pdf.status()).toBe(206); expect((await pdf.body()).length).toBe(256); expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  const response = await page.request.get(`/api/workspace/papers/${book}/reading?physical_page=541`);
  const value = await response.json(); expect(value.total_chunks).toBeGreaterThan(2000); expect(value.chunks.length).toBeGreaterThan(0); expect(value.chunks.every((c: { page_number: number }) => c.page_number === 541)).toBeTruthy();
  await page.getByLabel("跳转页码").fill("541"); await page.getByRole("button", { name: "前往", exact: true }).click();
  await expect(page.locator('[data-page="541"] canvas')).toBeVisible();
  expect(await page.locator(".sg-pdfpage canvas").evaluateAll(elements => elements.filter(element => (element as HTMLCanvasElement).width > 0 && (element as HTMLCanvasElement).height > 0).length)).toBeLessThan(12);
});

test("后端故障有明确状态且页面可恢复", async ({ page }) => {
  await page.route("**/api/workspace/papers?*", route => route.fulfill({ status: 502, json: { message: "后端停止测试" } }));
  await page.goto("/"); await expect(page.getByRole("alert").filter({ hasText: "后端停止测试" })).toBeVisible();
  await page.unroute("**/api/workspace/papers?*"); await page.reload(); await expect(page.locator(".sg-paper-card").first()).toBeVisible();
});
