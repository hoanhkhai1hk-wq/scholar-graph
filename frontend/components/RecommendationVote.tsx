"use client";
import { useState } from "react";
import { clientUrl } from "@/lib/api";
export default function RecommendationVote({ paperId, seedId, onChanged }: { paperId: string; seedId: string; onChanged: () => void }) {
  const [vote, setVote] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(next: string) { setBusy(true); setError(""); try { const response = await fetch(clientUrl("/recommendations/feedback"), { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ paper_id: paperId, seed_paper_id: seedId, vote: next }) }); if (!response.ok) throw new Error((await response.json()).message ?? "反馈未保存。"); setVote(next); onChanged(); } catch (cause) { setError(cause instanceof Error ? cause.message : "反馈未保存。"); } finally { setBusy(false); } }
  return <div><div className="sg-feedback"><button disabled={busy} aria-pressed={vote === "like"} onClick={() => void submit("like")}>有帮助</button><button disabled={busy} aria-pressed={vote === "dislike"} onClick={() => void submit("dislike")}>不相关</button></div>{error ? <p role="alert">{error}</p> : null}</div>;
}
