"use client";

import { useEffect, useRef, useState } from "react";
import { workspacePost, workspaceRequest, workspaceUrl } from "@/lib/workspace";
import { isFinalAnswer, parseSseChunk } from "@/lib/sse";
import type { CompareResult, PaperMeta, QAAnswer } from "@/lib/types";
import QaAnswerView from "./QaAnswerView";
import ResearchAnswerView, { type ResearchAnswer } from "./ResearchAnswerView";

type Message = { question: string; answer?: QAAnswer; research?: ResearchAnswer; comparison?: CompareResult; error?: string };
const stages: Record<string, string> = { plan: "确定需要查找的材料", query: "理解中文问题，转换中英文检索词", retrieve: "检索论文原文", qa: "根据证据组织回答", validate: "检查原文引用和数字", refuse: "检查是否有足够证据" };

export default function ResearchChat({ papers, initialPaperIds = [], compact = false }: { papers: PaperMeta[]; initialPaperIds?: string[]; compact?: boolean }) {
  const [selected, setSelected] = useState(initialPaperIds);
  const [question, setQuestion] = useState("");
  const [filter, setFilter] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState("");
  const [mode, setMode] = useState("");
  const [scopeLoaded, setScopeLoaded] = useState(compact || initialPaperIds.length > 0);
  const abort = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const scope = selected.slice().sort().join(",");
  const storageKey = `sg.research.${scope}`;

  useEffect(() => {
    try { const raw = localStorage.getItem(storageKey); setMessages(raw ? JSON.parse(raw) : []); } catch { setMessages([]); }
    setStatus("");
    let stopped = false;
    const sessionKey = `sg.session.${scope}`, sessionId = localStorage.getItem(sessionKey);
    if (sessionId) void workspaceRequest<{ messages: { question: string; answer?: QAAnswer | CompareResult | ResearchAnswer; error?: { message: string }; status: string }[] }>(`/sessions/${sessionId}`).then(session => {
      if (stopped || abort.current) return;
      const restored: Message[] = session.messages.slice(-30).map(item => ({ question: item.question,
        ...(item.answer && "kind" in item.answer && item.answer.kind === "research_answer" ? { research: item.answer as ResearchAnswer } : item.answer && isFinalAnswer(item.answer as unknown as Record<string, unknown>) ? { answer: item.answer as QAAnswer } : item.answer && "per_paper" in item.answer ? { comparison: item.answer as CompareResult } : {}),
        ...(item.error ? { error: item.error.message } : item.status === "cancelled" ? { error: "该次回答已停止，可重新提问。" } : {}) }));
      if (restored.length) setMessages(restored);
    }).catch(() => { if (!stopped) localStorage.removeItem(sessionKey); });
    return () => { stopped = true; abort.current?.abort(); };
  }, [storageKey]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [messages, status]);
  useEffect(() => { if (compact || initialPaperIds.length) return; const id = new URLSearchParams(window.location.search).get("paper"); if (id && papers.some(p => p.id === id)) setSelected([id]); else { try { const saved = JSON.parse(localStorage.getItem("sg.research.scope") ?? "[]"); if (Array.isArray(saved)) setSelected(saved.filter(id => typeof id === "string" && papers.some(p => p.id === id)).slice(0, 10)); } catch { /* Empty scope stays usable. */ } } setScopeLoaded(true); }, []);
  useEffect(() => { if (scopeLoaded && !compact) localStorage.setItem("sg.research.scope", JSON.stringify(selected)); }, [selected, scopeLoaded, compact]);

  function save(next: Message[]) {
    setMessages(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next.slice(-30))); } catch { /* Conversation remains available in memory if storage is full. */ }
  }

  async function send(retryQuestion?: string) {
    const currentQuestion = (retryQuestion ?? question).trim();
    if (running || !selected.length || selected.length > 10 || !currentQuestion) return;
    const next = [...messages, { question: currentQuestion }];
    save(next); setQuestion(""); setRunning(true); setMode(""); setStatus("正在连接研究服务…");
    const controller = new AbortController(); abort.current = controller;
    let finalReceived = false, refused = false;
    try {
      const sessionKey = `sg.session.${scope}`;
      let sessionId = localStorage.getItem(sessionKey);
      if (!sessionId) {
        const session = await workspacePost<{ id: string }>("/sessions", { paper_ids: selected });
        sessionId = session.id;
        localStorage.setItem(sessionKey, sessionId);
      }
      const response = await fetch(workspaceUrl(`/sessions/${sessionId}/messages/stream`), { method: "POST", headers: { "content-type": "application/json", accept: "text/event-stream" }, body: JSON.stringify({ question: currentQuestion }), signal: controller.signal });
      if (!response.ok) {
        const value = await response.json().catch(() => null);
        throw new Error(value?.message ?? `研究服务暂时不可用（${response.status}）`);
      }
      if (!response.body) throw new Error("服务没有返回回答数据。");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      try {
        while (true) {
          const chunk = await reader.read(); if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          const parsed = parseSseChunk(buffer); buffer = parsed.rest;
          for (const event of parsed.events) {
            const data = event.data as Record<string, unknown>;
            if (event.event === "mode") setMode(data.mode === "evidence_refusal" ? "未找到可引用原文" : data.mode === "deepseek" ? "模型回答 · 原文取证" : "原文摘录模式");
            if (event.event === "node_start") setStatus(stages[String(data.node)] ?? "处理论文材料");
            if (event.event === "error") throw new Error(String(data.message ?? "本次回答未通过校验，请重试。"));
            if (event.event === "final") {
              refused = data.refused === true;
              if (data.kind === "research_answer" && Array.isArray(data.paragraphs) && Array.isArray(data.calculations)) { next[next.length - 1] = { question: currentQuestion, research: data as unknown as ResearchAnswer }; }
              else if (isFinalAnswer(data)) { next[next.length - 1] = { question: currentQuestion, answer: data }; }
              else if (Array.isArray(data.per_paper) && Array.isArray(data.evidence_table) && typeof data.synthesis === "string") { next[next.length - 1] = { question: currentQuestion, comparison: data as unknown as CompareResult }; }
              else throw new Error("回答格式不完整，未展示为最终结果。");
              finalReceived = true; save([...next]);
            }
          }
        }
      } finally { reader.releaseLock(); }
      if (!finalReceived) throw new Error("连接已结束，但没有收到经校验的最终回答。请重试。");
      setStatus(refused ? "未找到足够的原文依据，或题设需要纠正。" : "本次回答已完成");
    } catch (error) {
      const cancelled = controller.signal.aborted;
      if (!finalReceived) { next[next.length - 1] = { question: currentQuestion, error: cancelled ? "已停止本次回答，可以重新提问。" : error instanceof Error ? error.message : "回答未完成，请重试。" }; save([...next]); }
      setStatus(cancelled ? "已停止" : "本次回答未完成");
    } finally { setRunning(false); abort.current = null; }
  }

  return <div className="sg-chat">
    {!compact ? <div className="sg-chat__papers"><label className="sg-field">本次研究的论文（已选 {selected.length}，最多 10 篇）<input className="sg-input" placeholder="搜索论文标题" value={filter} onChange={e => setFilter(e.target.value)} /></label><div className="sg-chat__paper-list">{papers.filter(p => (p.title ?? p.arxiv_id ?? p.id).toLowerCase().includes(filter.toLowerCase())).map(p => <label className="sg-chat__paper" key={p.id}><input type="checkbox" checked={selected.includes(p.id)} disabled={running || (!selected.includes(p.id) && selected.length >= 10)} onChange={() => setSelected(ids => ids.includes(p.id) ? ids.filter(id => id !== p.id) : [...ids, p.id])} /><span>{p.title ?? p.arxiv_id ?? `未命名论文 · ${p.page_count ?? "未知"} 页`}</span></label>)}</div>{!papers.length ? <p>论文库为空，请先上传论文。</p> : null}</div> : null}
    <p className="sg-chat__scope">{compact ? "当前论文：" : `本次回答范围：${selected.length} 篇`}{compact ? papers.find(p=>p.id===selected[0])?.title : null}</p><div className="sg-form" aria-label="提问示例"><button className="sg-btn sg-btn--ghost" disabled={running || !selected.length} onClick={() => setQuestion(selected.length > 1 ? "这几篇论文各自研究什么？" : "这篇论文主要讲什么？")}>概括主要内容</button><button className="sg-btn sg-btn--ghost" disabled={running || !selected.length} onClick={() => setQuestion(selected.length > 1 ? "这几篇论文有哪些共同点和区别？" : "这篇论文的创新点是什么？")}>{selected.length > 1 ? "比较共同点与区别" : "了解创新点"}</button></div><div className="sg-chat__messages" aria-live="polite" aria-busy={running}>
      {!messages.length ? <div className="sg-chat__empty"><strong>带着问题阅读原文</strong><p>{selected.length > 1 ? "已选多篇，可以直接问“它们有什么关联？”；系统会区分共同主题和有证据的承袭关系。" : "可以直接问“这篇论文讲什么？”或“创新点是什么？”，也可以提具体问题。"} 回答中的证据可点击查看原文。</p></div> : null}
      {messages.map((message, i) => <div key={i}><div className="sg-chat__question">{message.question}</div><div className="sg-chat__answer">{message.research ? <ResearchAnswerView answer={message.research} /> : null}{message.answer ? <QaAnswerView answer={message.answer} /> : null}{message.comparison ? <><p className="sg-prose">{message.comparison.synthesis}</p>{message.comparison.per_paper.map((answer, n) => <QaAnswerView key={n} answer={answer} title={`论文 ${n + 1}`} />)}</> : null}{message.research?.refused ? <button className="sg-btn sg-btn--ghost" disabled={running} onClick={() => void send(message.question)}>重新检索此问题</button> : null}{message.error ? <div role="alert" className="sg-error"><p>{message.error}</p><button className="sg-btn sg-btn--ghost" onClick={() => setQuestion(message.question)}>重新编辑问题</button></div> : null}</div></div>)}
      {status ? <div className="sg-chat__status" role="status">{status}</div> : null}<div ref={end} />
    </div>
    <div className="sg-chat__composer"><textarea className="sg-input" aria-label="研究问题" placeholder={selected.length ? "输入你的问题…" : "先选择论文，再输入问题"} value={question} onChange={e => setQuestion(e.target.value)} disabled={running} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} /><div className="sg-chat__actions"><span className="sg-mono">{mode || (selected.length > 1 ? "跨篇研究" : "单篇研究")}</span>{running ? <button className="sg-btn sg-btn--ghost" onClick={() => abort.current?.abort()}>停止回答</button> : <button className="sg-btn" disabled={!selected.length || !question.trim()} title={!selected.length ? "请先选择论文" : !question.trim() ? "请输入问题" : "发送问题"} onClick={() => void send()}>发送</button>}</div></div>
  </div>;
}
