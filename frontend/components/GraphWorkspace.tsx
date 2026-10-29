"use client";
import Link from "next/link";
import { useEffect,useState } from "react";
import { workspacePost } from "@/lib/workspace";
import type { GraphView, PaperMeta } from "@/lib/types";
import PaperPicker from "./PaperPicker";
import GraphCanvas from "./GraphCanvas";
import AnchorTag from "./AnchorTag";
import GraphResearch from "./GraphResearch";
import GraphDiagnostics from "./GraphDiagnostics";
import AsyncStatus from "./AsyncStatus";
import EmptyState from "./EmptyState";
const LEVELS = { cornerstone: "本地核心", derived: "衍生节点", isolated: "尚无已匹配关系" };
export default function GraphWorkspace({ papers }: { papers: PaperMeta[] }) {
  const [selected, setSelected] = useState<string[]>([]), [data, setData] = useState<GraphView | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false), [research,setResearch]=useState(false),[version,setVersion]=useState(0);
  useEffect(()=>{try{const ids=JSON.parse(localStorage.getItem('sg.graph.scope')??'[]');if(Array.isArray(ids))setSelected(ids.filter(id=>papers.some(p=>p.id===id)).slice(0,100));}catch{}},[papers]);
  function choose(ids:string[]){setSelected(ids);localStorage.setItem('sg.graph.scope',JSON.stringify(ids));}
  async function submit() { setBusy(true); setError("");setResearch(false); try { setData(await workspacePost<GraphView>('/graph/rebuild',{paper_ids:selected,compact:true}));setVersion(v=>v+1); } catch (cause) { setError(cause instanceof Error ? cause.message : "图谱未能生成。"); } finally { setBusy(false); } }
  const numbers = new Map(data?.nodes.map((n,i)=>[n.paper_id,String(i+1).padStart(2,"0")])??[]);
  const names = new Map(data?.nodes.map(n => [n.paper_id, n.title ?? "标题未提取"]) ?? []);
  const ranked = [...(data?.nodes ?? [])].sort((a, b) => b.pagerank - a.pagerank);
  const verified = data?.edges.filter(e => e.status === "verified") ?? [];
  const pairCount = new Set(verified.map(e => `${e.from_paper_id}:${e.to_paper_id}`)).size;
  const scope=data?.nodes.map(n=>n.paper_id)??[];
  const proofs=(data?.diagnostics as unknown as {edge_evidence?:{evidence_kind?:string}[]})?.edge_evidence??[];
  const bibliography=proofs.filter(p=>p.evidence_kind==='bibliography_identity').length;
  const allButton=<button className="sg-btn sg-btn--ghost" disabled={busy||!papers.length||papers.length>100} title={!papers.length?'先上传论文':undefined} onClick={()=>choose(papers.map(p=>p.id))}>全选这 {papers.length} 篇论文</button>;
  return <><section className="sg-section"><h2 className="sg-section__title">选择研究文献</h2><p>选择同一方向的论文，查看它们之间的引用网络。最多可选一百篇；本地核心仅代表当前文献集合的引用位置。</p><PaperPicker papers={papers} selected={selected} onChange={choose} disabled={busy} multiple label="图谱论文" /><div className="sg-form"><button className="sg-btn" disabled={busy || !selected.length || selected.length > 100} title={!selected.length ? "请先选择论文" : undefined} onClick={() => void submit()}>{busy ? "正在核对引用与计算排名…" : `生成图谱（已选 ${selected.length}）`}</button></div></section>
  <div className="sg-form">{allButton}</div>{error ? <p role="alert" className="sg-error">{error}</p> : null}{busy ? <AsyncStatus label="正在核对引用并构建图谱…" rows={6} /> : null}{data && (busy || error) ? <p role="status" className="sg-note">下方暂时保留上一次成功生成的图谱，尚未替换为本次结果。</p> : null}{data ? <><section className="sg-section"><h2 className="sg-section__title">引用网络</h2><p>{data.nodes.length} 篇论文，{pairCount} 条论文间引用关系，{data.layers.isolated.length} 个孤立节点。</p><p>{verified.length} 处原文依据，其中 {bibliography} 处定位到参考文献条目，其余定位到正文；箭头从引用方指向被引方。</p><GraphCanvas graph={data} />{scope.length <= 20 ? <button onClick={()=>setResearch(true)} className="sg-btn">依据当前图谱生成综述与未来方向</button> : <p>生成综述请将论文集合缩小到二十篇以内。</p>}</section>
  {research?<GraphResearch key={[...scope].sort().join(',')} paperIds={scope}/>:null}
  <section className="sg-section"><h2 className="sg-section__title">核心与衍生关系</h2><p>排名使用当前集合内部的引用关系计算，无法证明某篇论文是整个领域的基石。范围外文献不会作为孤立的占位节点加入。</p><table className="sg-table"><thead><tr><th>编号</th><th>论文</th><th>年份</th><th>引用网络分数</th><th>位置</th></tr></thead><tbody>{ranked.map(node => <tr key={node.paper_id}><td>{numbers.get(node.paper_id)}</td><td><Link href={`/read/${node.paper_id}`}>{node.title ?? "标题未提取"}</Link></td><td>{node.year ?? "未提取"}</td><td>{node.pagerank.toFixed(6)}</td><td>{LEVELS[node.level]}</td></tr>)}</tbody></table></section>
  <section className="sg-section"><h2 className="sg-section__title">逐条查证引用</h2>{data.edges.length ? <table className="sg-table"><thead><tr><th>引用论文</th><th>被引论文</th><th>原文依据</th></tr></thead><tbody>{data.edges.map((edge, i) => <tr key={i}><td>{names.get(edge.from_paper_id)}</td><td>{names.get(edge.to_paper_id)}</td><td>{edge.status === "verified" ? <AnchorTag anchor={edge.anchor} /> : "尚未核对"}</td></tr>)}</tbody></table> : <p>当前集合没有匹配出的引用关系，可以增加同一研究方向的论文。</p>}</section>
  <GraphDiagnostics key={version} paperIds={scope} unresolved={data.diagnostics.unresolved_references.length}/></> : !busy && !error ? <EmptyState variant="graph" title="从一组论文开始构图" hint="先选择同一方向的论文，再核对它们的引用关系。节点和排名均来自所选原文。" /> : null}</>;
}
