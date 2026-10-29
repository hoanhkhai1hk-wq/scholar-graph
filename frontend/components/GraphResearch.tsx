"use client";
import {useCallback,useEffect,useState} from "react";
import type {Anchor} from "@/lib/types";
import {workspacePost} from "@/lib/workspace";
import TaskMonitor,{type WorkspaceTask} from "./TaskMonitor";
import AnchorTag from "./AnchorTag";
import FutureDirections,{type Future} from "./FutureDirections";
interface Review{title:string;review_notice:string;sections:{title:string;paragraphs:{text:string;type:string;citations:{quote:string;anchor:Anchor}[]}[]}[];references:{paper_id:string;title:string|null;year:number|null;authors:string[]}[];}
export default function GraphResearch({paperIds}:{paperIds:string[]}){
  const key=`sg.graph.research.${[...paperIds].sort().join(",")}`;
  const [reviewTask,setReviewTask]=useState(""),[futureTask,setFutureTask]=useState(""),[review,setReview]=useState<Review|null>(null),[future,setFuture]=useState<Future|null>(null),[busy,setBusy]=useState(false),[running,setRunning]=useState<Record<string,boolean>>({}),[error,setError]=useState("");
  useEffect(()=>{setReviewTask(localStorage.getItem(key+".review")??"");setFutureTask(localStorage.getItem(key+".future")??"");},[key]);
  const receive=useCallback((value:NonNullable<WorkspaceTask['result']>)=>{if(value.document)setReview(value.document as Review);if(value.future)setFuture(value.future as Future);},[]);
  const active=Object.values(running).some(Boolean);
  async function generate(kind:"review"|"future"){
    setBusy(true);setError("");try{const task=await workspacePost<WorkspaceTask>("/writing/tasks",{kind,paper_ids:paperIds,idea:kind==="review"?"结合当前所选论文的真实引用图谱，生成有原文依据的简短综述；所有事实和参考文献均限定在所选集合，区分贡献与研究设想。":"提取所选论文明确的未来工作，对照较新原文和最近研究，排除已尝试的方向，证据不足则标记不确定。"});if(kind==="review")setReviewTask(task.id);else setFutureTask(task.id);localStorage.setItem(key+"."+kind,task.id);setRunning(v=>({...v,[kind]:true}));}catch(cause){setError(cause instanceof Error?cause.message:"研究任务未能创建。");}finally{setBusy(false);}}
  return <section className="sg-section" aria-label="图谱分析与生成"><h2 className="sg-section__title">基于当前图谱的研究</h2><p>范围固定为本次图谱的 {paperIds.length} 篇论文。综述仅引用本集合；未来方向另检索更新研究并标明年份和出处。生成材料会发送给已配置的DeepSeek。</p><div className="sg-form"><button className="sg-btn" disabled={busy||active} onClick={()=>void generate('review')}>生成图谱综述</button><button className="sg-btn sg-btn--ghost" disabled={busy||active} onClick={()=>void generate('future')}>核查未来方向</button></div>{error?<p role="alert" className="sg-error">{error}</p>:null}
  {reviewTask?<TaskMonitor taskId={reviewTask} onResult={receive} onTaskChange={id=>{setReviewTask(id);localStorage.setItem(key+'.review',id);setRunning(v=>({...v,review:true}));}} onStatus={s=>setRunning(v=>({...v,review:['queued','running','cancelling'].includes(s)}))}/>:null}
  {futureTask?<TaskMonitor taskId={futureTask} onResult={receive} onTaskChange={id=>{setFutureTask(id);localStorage.setItem(key+'.future',id);setRunning(v=>({...v,future:true}));}} onStatus={s=>setRunning(v=>({...v,future:['queued','running','cancelling'].includes(s)}))}/>:null}
  {review?<article aria-label="图谱综述结果"><h3>{review.title}</h3><p className="sg-note">{review.review_notice}</p>{review.sections.map((s,i)=><section key={i}><h4>{s.title}</h4>{s.paragraphs.map((p,j)=><div key={j} className="sg-writing-paragraph"><span className="sg-tag">{p.type==='proposal'?"研究设想 · 尚未验证":"文献归纳"}</span><p className="sg-prose">{p.text}</p>{p.citations.map((c,k)=><details key={k}><summary>查看原文依据 {k+1}</summary><blockquote>{c.quote}</blockquote><AnchorTag anchor={c.anchor}/></details>)}</div>)}</section>)}<h4>参考文献</h4><ol>{review.references.map(r=><li key={r.paper_id}>{r.authors.join(', ')} · {r.year??'年份待核对'} · {r.title} <a href={`/read/${r.paper_id}`}>阅读原文</a></li>)}</ol></article>:null}
  {future?<FutureDirections value={future}/>:null}</section>;
}
