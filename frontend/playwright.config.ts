import { defineConfig } from "@playwright/test";
const evidence = process.env.SG_TEST_RUN ? `../data/workbench-runtime/browser-runs/${process.env.SG_TEST_RUN}` : "../data/workbench-runtime";
export default defineConfig({
  testDir: "./e2e", timeout: 90000, expect: { timeout: 15000 }, workers: 1, retries: 0,
  reporter: [["list"], ["json", { outputFile: `${evidence}/browser-results.json` }]],
  outputDir: `${evidence}/browser-artifacts`,
  use: { baseURL: process.env.SG_TEST_URL || "http://127.0.0.1:3200", channel: "chrome", headless: true, locale: "zh-CN", trace: "retain-on-failure", screenshot: "only-on-failure" },
});
