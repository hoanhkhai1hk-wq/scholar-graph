/**
 * 后端端点清单。
 * 来源：docs/api-draft-v1.md「端点清单」与 backend/README.md。
 *
 * 模块六完成后后端 **19/19 条端点已全部落地，未落地清单为 0**，
 * 因此本文件不再维护「未落地清单」，页面也不再出现
 * 「后端接口未落地，暂不可用」的占位。
 */

export type EndpointArea =
  | "library"
  | "paper"
  | "qa"
  | "graph"
  | "retrieval"
  | "writing";

export interface EndpointSpec {
  method: "GET" | "POST";
  path: string;
  area: EndpointArea;
  label: string;
  page: string;
}

export const LANDED_ENDPOINTS: EndpointSpec[] = [
  { method: "POST", path: "/papers", area: "library", label: "单篇上传", page: "/upload" },
  { method: "POST", path: "/papers/batch", area: "library", label: "批量上传", page: "/upload" },
  { method: "GET", path: "/papers", area: "library", label: "论文列表", page: "/" },
  { method: "GET", path: "/papers/{paper_id}", area: "paper", label: "论文详情", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/parse-status", area: "paper", label: "解析状态", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/chunks", area: "paper", label: "分块列表", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/references", area: "paper", label: "参考文献", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/citation-links", area: "paper", label: "引用对应", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/dedup-decision", area: "paper", label: "去重裁决", page: "/papers/{id}" },
  { method: "GET", path: "/papers/{paper_id}/diff-summary", area: "paper", label: "版本差异", page: "/papers/{id}" },
  { method: "POST", path: "/papers/{paper_id}/qa", area: "qa", label: "单篇问答", page: "/qa" },
  { method: "POST", path: "/compare", area: "qa", label: "跨篇对比", page: "/qa" },
  { method: "GET", path: "/graph", area: "graph", label: "引用图谱", page: "/graph" },
  { method: "POST", path: "/retrieval/search", area: "retrieval", label: "检索", page: "/retrieval" },
  { method: "POST", path: "/retrieval/fetch", area: "retrieval", label: "公开抓取", page: "/retrieval" },
  { method: "GET", path: "/recommendations", area: "retrieval", label: "智能推荐", page: "/retrieval" },
  { method: "POST", path: "/frameworks", area: "writing", label: "综述框架", page: "/writing" },
  { method: "POST", path: "/reviews", area: "writing", label: "摘录草稿", page: "/writing" },
  { method: "POST", path: "/charts/csv", area: "writing", label: "CSV 图表", page: "/writing" },
];

export function landedByArea(area: EndpointArea): EndpointSpec[] {
  return LANDED_ENDPOINTS.filter((item) => item.area === area);
}
