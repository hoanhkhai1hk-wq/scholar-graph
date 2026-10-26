/**
 * 把 pdf.js 的 worker 从 node_modules 复制到 public/，供浏览器按 URL 加载。
 *
 * 不复制 pdf.js 源码进仓库：worker 是构建产物，由本脚本在 build/dev 前生成，
 * 已在 .gitignore 中排除。pdf.js（pdfjs-dist）协议为 Apache-2.0，
 * 登记见 docs/open-source-register.md。
 */
import { copyFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const source = path.join(root, "node_modules", "pdfjs-dist", "build", "pdf.worker.min.mjs");
const targetDir = path.join(root, "public");
const target = path.join(targetDir, "pdf.worker.min.mjs");

if (!existsSync(source)) {
  console.error("[pdf.worker] 未找到源文件，请先 npm install：", source);
  process.exit(1);
}

await mkdir(targetDir, { recursive: true });
await copyFile(source, target);
console.log("[pdf.worker] 已复制 -> public/pdf.worker.min.mjs");
