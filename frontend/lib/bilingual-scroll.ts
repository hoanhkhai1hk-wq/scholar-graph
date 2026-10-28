/** Map matching paragraph boundaries, including progress inside a paragraph. */
export type ScrollAnchor = { id: string; top: number };
export function mapBilingualScroll(top: number, sourceMax: number, targetMax: number, source: ScrollAnchor[], target: ScrollAnchor[]) {
  const clamp = (value: number, maximum: number) => Math.max(0, Math.min(maximum, value));
  if (!source.length || !target.length || sourceMax <= 0) return { top: 0, id: source[0]?.id ?? null, atBottom: false };
  if (top >= sourceMax - 1) return { top: Math.max(0, targetMax), id: source[source.length - 1].id, atBottom: true };
  const targetPositions = new Map(target.map(row => [row.id, row.top]));
  const paired = source.filter(row => targetPositions.has(row.id));
  let index = 0;
  while (index + 1 < paired.length && paired[index + 1].top <= top) index++;
  const row = paired[index];
  if (!row) return { top: clamp(top / sourceMax * targetMax, targetMax), id: null, atBottom: false };
  const next = paired[index + 1];
  const end = next?.top ?? sourceMax;
  const targetStart = targetPositions.get(row.id)!;
  const targetEnd = next ? targetPositions.get(next.id)! : targetMax;
  const progress = clamp((top - row.top) / Math.max(1, end - row.top), 1);
  const desired = targetStart + progress * (targetEnd - targetStart);
  return { top: clamp(desired, targetMax), id: row.id, atBottom: desired >= targetMax - 1 };
}
