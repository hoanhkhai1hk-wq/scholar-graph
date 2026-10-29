"use client";
import {useState} from "react";
import {workspaceRequest} from "@/lib/workspace";
export default function GraphDiagnostics({paperIds,unresolved}:{paperIds:string[];unresolved:number}){
  const [value,setValue]=useState<unknown>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  async function load(){if(value||busy)return;setBusy(true);setError("");try{const params=new URLSearchParams();paperIds.forEach(id=>params.append('paper_ids',id));setValue(await workspaceRequest('/graph?'+params.toString()));}catch(cause){setError(cause instanceof Error?cause.message:'完整依据读取失败。');}finally{setBusy(false);}}
  return <details className="sg-section" onToggle={e=>{if(e.currentTarget.open)void load();}}><summary>诊断信息与原始图谱</summary><p>未匹配参考文献 {unresolved} 项，可能位于所选集合之外或身份信息不足。展开后才读取完整原文依据，减少首次加载。</p><p>本地核心须有入边且PageRank超过本集合均匀基线；无已核对入边或出边的节点列为孤立，其余列为衍生。</p>{busy?<p role="status">正在读取完整引用依据…</p>:null}{error?<p role="alert">{error}<button onClick={()=>void load()}>重试读取</button></p>:null}{value?<pre className="sg-code">{JSON.stringify(value,null,2)}</pre>:null}</details>;
}
