/** Display summaries preserve every original error in the diagnostic disclosure. */
export function trackingErrorGroups(errors: { message: string }[]) {
  const groups = new Map<string, number>();
  for (const error of errors) {
    const message = error.message === "arXiv 公共接口连接失败，未编造记录。"
      ? "arXiv 请求未完成，请检查网络或稍后重试。" : error.message;
    groups.set(message, (groups.get(message) ?? 0) + 1);
  }
  return [...groups].map(([message, count]) => ({ message, count }));
}
