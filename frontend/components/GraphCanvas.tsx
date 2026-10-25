"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import type { GraphView } from "@/lib/types";

/**
 * 局域引用图谱画布（Cytoscape.js）。
 *
 * 三条硬规则：
 * 1. 只画 status=verified 的边；unverified 边不画，也不画成已核验样式。
 * 2. 孤立节点照样显示，不因为没边就隐藏。
 * 3. 基石（cornerstone）节点高亮，与衍生/孤立区分开。
 *
 * 配色沿用已确认 token，不用渐变、不用 emoji。
 */
const COLOR = {
  cornerstone: "#14544b",
  derived: "#3c6e8f",
  isolated: "#8a877e",
  nodeBorder: "#ffffff",
  edge: "#7a6a2e",
  label: "#1b1b19",
  canvas: "#f7f6f3",
};

export default function GraphCanvas({ graph }: { graph: GraphView }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<Core | null>(null);
  const router = useRouter();

  const verifiedEdges = graph.edges.filter((edge) => edge.status === "verified");
  const unverifiedCount = graph.edges.length - verifiedEdges.length;
  const isolatedCount = graph.layers.isolated.length;

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [];

    for (const node of graph.nodes) {
      const level = node.level;
      const isCornerstone = level === "cornerstone";
      elements.push({
        data: {
          id: node.paper_id,
          label:
            (node.title ?? "（标题未提取）").slice(0, 28) +
            ((node.title ?? "").length > 28 ? "…" : ""),
          level,
          pagerank: node.pagerank,
          paperId: node.paper_id,
        },
      });
    }

    // 只画已核验边，引用方向为 引用方 → 被引方
    for (const edge of graph.edges) {
      if (edge.status !== "verified") continue;
      elements.push({
        data: {
          id: `${edge.from_paper_id}->${edge.to_paper_id}`,
          source: edge.from_paper_id,
          target: edge.to_paper_id,
        },
      });
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: "cose", animate: false, randomize: false, padding: 40 },
      style: [
        {
          selector: "node",
          style: {
            "background-color": COLOR.isolated,
            "border-width": 2,
            "border-color": COLOR.nodeBorder,
            label: "data(label)",
            "font-size": 11,
            color: "data(level)",
            "text-valign": "center",
            "text-halign": "right",
            "text-margin-x": 6,
            "text-outline-width": 2,
            "text-outline-color": COLOR.canvas,
            width: 30,
            height: 30,
          },
        },
        {
          selector: 'node[level = "cornerstone"]',
          style: {
            "background-color": COLOR.cornerstone,
            width: 46,
            height: 46,
            "border-width": 3,
            "font-weight": 700,
          },
        },
        {
          selector: 'node[level = "derived"]',
          style: {
            "background-color": COLOR.derived,
            width: 34,
            height: 34,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": COLOR.edge,
            "target-arrow-color": COLOR.edge,
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 0.9,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": COLOR.cornerstone,
            "border-width": 4,
          },
        },
      ],
      minZoom: 0.2,
      maxZoom: 3,
    });

    // 点节点进该论文详情页
    cy.on("tap", "node", (event) => {
      const paperId = event.target.data("paperId") as string;
      if (paperId) {
        router.push(`/papers/${paperId}`);
      }
    });

    instanceRef.current = cy;

    return () => {
      cy.destroy();
      instanceRef.current = null;
    };
  }, [graph, router]);

  function zoom(factor: number) {
    const cy = instanceRef.current;
    if (!cy) return;
    const next = cy.zoom() * factor;
    cy.zoom({ level: next, renderedPosition: { x: 200, y: 150 } });
  }

  function fit() {
    instanceRef.current?.fit(undefined, 40);
  }

  return (
    <div className="sg-graph">
      <div className="sg-graph__toolbar">
        <button className="sg-btn sg-btn--ghost" type="button" onClick={() => zoom(1.2)}>
          放大
        </button>
        <button className="sg-btn sg-btn--ghost" type="button" onClick={() => zoom(0.8)}>
          缩小
        </button>
        <button className="sg-btn sg-btn--ghost" type="button" onClick={fit}>
          适应窗口
        </button>
        <span className="sg-mono">滚轮缩放 · 拖拽平移 · 点节点进详情</span>
      </div>

      <div className="sg-graph__canvas" ref={containerRef} />

      <div className="sg-graph__legend">
        <span className="sg-legend-item">
          <i className="sg-swatch sg-swatch--cornerstone" />
          基石 cornerstone
        </span>
        <span className="sg-legend-item">
          <i className="sg-swatch sg-swatch--derived" />
          衍生 derived
        </span>
        <span className="sg-legend-item">
          <i className="sg-swatch sg-swatch--isolated" />
          孤立 isolated
        </span>
        <span className="sg-legend-item">
          <i className="sg-swatch sg-swatch--edge" />
          已核验引用边
        </span>
      </div>

      <p className="sg-mono">
        画布只画 {verifiedEdges.length} 条已核验（verified）边
        {unverifiedCount > 0
          ? `；另有 ${unverifiedCount} 条无锚点边未画入画布，避免被误读为已核验，数量与明细见下方附表`
          : "，没有未核验边"}
        ；孤立节点 {isolatedCount} 个照常显示，不因无边而隐藏。
      </p>
    </div>
  );
}
