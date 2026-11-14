import type { EvidenceLocation } from "./types";

/** All regions share the parser's normalized top-left page coordinates. */
export function regionFromBox(box: EvidenceLocation["bbox"] | undefined) {
  if (!box || box.length !== 4 || box.some(v => !Number.isFinite(v) || v < 0 || v > 1)) return null;
  const [x0, y0, x1, y1] = box;
  return x0 < x1 && y0 < y1 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
}
