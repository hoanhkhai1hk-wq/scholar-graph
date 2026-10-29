// Real Chromium operations, real task results and actual downloaded Markdown.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('../../frontend/node_modules/playwright');
const base = path.resolve(__dirname, '../../data/code-order-20261029');
const out = path.join(base, process.argv[2]); fs.mkdirSync(out);
const pid = 'paper-0776f0af6f06613433bef8112cc493177534bcf42a91636c9739e789f76ec110';
const save = (name, value) => fs.writeFileSync(path.join(out, name), JSON.stringify(value, null, 2));
const expected = 'def forward(x):\n    # Keep this English comment.\n    return x + 1';
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage(), report = { page_errors: [], checks: [] };
  page.on('pageerror', error => report.page_errors.push(error.message));
  try {
    await ctx.tracing.start({ screenshots: true, snapshots: true, sources: false });
    await page.goto('http://127.0.0.1:3460/read/' + pid + '?page=2');
    await page.getByRole('tab', { name: '本页文本', exact: true }).click();
    const originalReturn = page.locator('.sg-reader .sg-source-text').filter({ hasText: 'return x + 1' });
    await originalReturn.waitFor();
    assert.match(await originalReturn.textContent(), /\n {4}return x \+ 1/);
    assert.equal(await originalReturn.evaluate(element => getComputedStyle(element).whiteSpace), 'pre-wrap');
    await originalReturn.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(out, 'source-indent.png') });
    report.checks.push('stored_source_visible_with_four_space_indent');
    await page.getByRole('tab', { name: '双语与翻译', exact: true }).click();
    const area = page.locator('.sg-translate');
    await area.getByRole('combobox').nth(0).selectOption('en');
    await area.getByRole('combobox').nth(1).selectOption('full');
    const pending = page.waitForResponse(response => response.url().endsWith('/translation-tasks') && response.request().method() === 'POST');
    await area.getByRole('button', { name: '开始翻译', exact: true }).click();
    const response = await pending; assert.equal(response.status(), 202); let task = await response.json();
    for (let n = 0; n < 300 && ['queued', 'running', 'cancelling'].includes(task.status); n++) {
      await page.waitForTimeout(500); task = await (await page.request.get('http://127.0.0.1:8160/api/v2/tasks/' + task.id)).json();
    }
    save('ui-translation-task.json', task); assert.equal(task.status, 'completed');
    report.ui_model_calls = task.result.translation.metadata.model_calls.length;
    report.ui_cache_hits = task.result.translation.metadata.cache_hits;
    await area.getByRole('heading', { name: /已校验译文/ }).waitFor();
    const detail = area.locator('details').filter({ has: page.getByText('查看全文排版译文', { exact: true }) });
    await detail.locator('summary').click();
    const code = detail.locator('pre code'); await code.waitFor(); assert.equal(await code.textContent(), expected);
    assert.equal(await code.locator('a').count(), 0);
    assert.equal(await detail.locator('[data-chunk-id]').count(), 21);
    const dl = page.waitForEvent('download'); await area.getByRole('button', { name: '导出译文', exact: true }).click();
    const download = await dl, file = path.join(out, 'downloaded-translation.md'); await download.saveAs(file);
    const markdown = fs.readFileSync(file, 'utf8'), body = /```python\n([\s\S]*?)\n```/.exec(markdown)[1];
    assert.equal(body, expected); assert.ok(!body.includes('<a '));
    report.checks.push('real_task_completed', 'markdown_rendered_without_code_anchors', 'download_matches_source_code');
    for (const [width, height] of [[1440, 900], [1366, 768], [1024, 768], [390, 844]]) {
      await page.setViewportSize({ width, height }); await code.scrollIntoViewIfNeeded();
      const dimensions = await page.evaluate(() => ({ viewport: innerWidth, width: document.documentElement.scrollWidth }));
      assert.ok(dimensions.width <= dimensions.viewport + 1, JSON.stringify(dimensions));
      report['viewport_' + width] = dimensions; await page.screenshot({ path: path.join(out, 'code-' + width + '.png') });
    }
    await page.reload(); await page.getByRole('tab', { name: '双语与翻译', exact: true }).click();
    await area.getByRole('heading', { name: /已校验译文/ }).waitFor(); report.checks.push('verified_task_survives_refresh');
    // Existing library, actual pre-fix task, no API mocks.
    const legacy = JSON.parse(fs.readFileSync(path.join(base, 'legacy-task.json'))).id;
    await page.goto('http://127.0.0.1:3440/');
    await page.evaluate(({ pid, legacy }) => localStorage.setItem('sg.translation.' + pid, legacy), { pid, legacy });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('http://127.0.0.1:3440/read/' + pid); await page.getByRole('tab', { name: '双语与翻译', exact: true }).click();
    await page.getByRole('heading', { name: /历史译文待重新校验/ }).waitFor();
    assert.ok(await page.getByRole('button', { name: '导出译文', exact: true }).isDisabled());
    await page.locator('.sg-translate [role=alert]').screenshot({ path: path.join(out, 'legacy-warning.png') });
    report.checks.push('actual_historical_translation_flagged_and_export_disabled');
    assert.deepEqual(report.page_errors, []); report.passed = true;
  } catch (error) {
    report.passed = false; report.failure = error.stack; await page.screenshot({ path: path.join(out, 'failure.png') }).catch(() => {}); process.exitCode = 1;
  } finally {
    save('result.json', report); console.log(JSON.stringify(report)); await ctx.tracing.stop({ path: path.join(out, 'trace.zip') }).catch(() => {}); await ctx.close(); await browser.close();
  }
})().catch(error => { console.log(error.stack); process.exitCode = 1; });
