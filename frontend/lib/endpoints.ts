/**
 * 后端未落地端点清单。
 * 来源：docs/api-draft-v1.md「端点清单」与 tests/reports/module-one-api-report.md
 * 「端点实施清单」——19 条中落地 10 条、未落地 9 条。
 *
 * 这些端点页面只保留占位并明标不可用，不伪造数据，不写成已接通。
 */

export type EndpointArea = "library" | "paper";

export interface EndpointSpec {
  method: "GET" | "POST";
  path: string;
  area: EndpointArea;
  label: string;
  reason: string;
}

export const UNLANDED_ENDPOINTS: EndpointSpec[] = [
  {
    method: "POST",
    path: "/papers/{paper_id}/qa",
    area: "paper",
    label: "单篇问答",
    reason: "模块二问答，不在模块一",
  },
  {
    method: "POST",
    path: "/compare",
    area: "paper",
    label: "跨篇对比",
    reason: "跨篇问答，不是版本差异；模块二",
  },
  {
    method: "POST",
    path: "/reviews",
    area: "paper",
    label: "综述生成",
    reason: "综述与写作，结构留待 v1.2",
  },
  {
    method: "POST",
    path: "/frameworks",
    area: "paper",
    label: "框架生成",
    reason: "写作辅助，框架结构留待 v1.2",
  },
  {
    method: "POST",
    path: "/charts/csv",
    area: "paper",
    label: "CSV 图表",
    reason: "模块六，只有 v1.1 契约已定义，接口未实现",
  },
  {
    method: "GET",
    path: "/graph",
    area: "library",
    label: "引用图谱",
    reason: "模块五，图谱结构留待 v1.2",
  },
  {
    method: "POST",
    path: "/retrieval/search",
    area: "library",
    label: "论文检索",
    reason: "检索推荐，不在模块一",
  },
  {
    method: "POST",
    path: "/retrieval/fetch",
    area: "library",
    label: "论文抓取",
    reason: "抓取任务专用失败结构仍待裁定",
  },
  {
    method: "GET",
    path: "/recommendations",
    area: "library",
    label: "智能推荐",
    reason: "检索推荐，分数与理由未定义",
  },
];

export function unlandedByArea(area: EndpointArea): EndpointSpec[] {
  return UNLANDED_ENDPOINTS.filter((item) => item.area === area);
}

/** 已落地并已接通的 10 条端点，用于说明页面取数范围 */
export const LANDED_ENDPOINTS: { method: string; path: string }[] = [
  { method: "POST", path: "/papers" },
  { method: "POST", path: "/papers/batch" },
  { method: "GET", path: "/papers" },
  { method: "GET", path: "/papers/{paper_id}" },
  { method: "GET", path: "/papers/{paper_id}/parse-status" },
  { method: "GET", path: "/papers/{paper_id}/chunks" },
  { method: "GET", path: "/papers/{paper_id}/references" },
  { method: "GET", path: "/papers/{paper_id}/citation-links" },
  { method: "GET", path: "/papers/{paper_id}/dedup-decision" },
  { method: "GET", path: "/papers/{paper_id}/diff-summary" },
];
