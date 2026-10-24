/**
 * MOCK DATA — 演示假数据，未接后端的统一出口。
 *
 * 全部数据取自 contracts/ 下 v1 与 v1.1 九份记录的 example：
 *   v1   —— PaperMeta / Chunk / ReferenceEntry / CitationLink / QAAnswer
 *   v1.1 —— ParseStatus / DedupDecision / DiffSummary / ChartOutput
 *
 * 使用约束：
 *   1. 字段集与契约 example 完全一致，任何契约外字段不得进入页面。
 *   2. 契约 example 之外的补充记录（如 paper-demo-002、paper-demo-003）
 *      仅为演示去重与新版本关系、无文本层分支而构造，沿用同一字段集。
 *   3. 这些数据是合成数据，不是真实论文，也不是后端实跑产物。
 */
export { default as paperMetaMock } from "./paper-meta.mock";
export { default as chunkMock } from "./chunk.mock";
export { default as referenceEntryMock } from "./reference-entry.mock";
export { default as citationLinkMock } from "./citation-link.mock";
export { default as qaAnswerMock } from "./qa-answer.mock";
export { default as parseStatusMock } from "./parse-status.mock";
export { default as dedupDecisionMock } from "./dedup-decision.mock";
export { default as diffSummaryMock } from "./diff-summary.mock";
export { default as chartOutputMock } from "./chart-output.mock";
