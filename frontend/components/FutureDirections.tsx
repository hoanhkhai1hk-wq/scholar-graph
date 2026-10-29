import type {Anchor,PaperMeta} from "@/lib/types";
import AnchorTag from "./AnchorTag";
type Candidate=PaperMeta&{candidate_origin?:string};
export interface Future{notice:string;directions:{topic:string;quote:string;anchor:Anchor;searched_at:string;decision:string;source_year?:number|null;reason:string;
  candidates:Candidate[];matches:{candidate_id:string;quote:string;year?:number|null;anchor?:Anchor}[];
  remaining_candidate?:{topic:string;notice:string};error?:{message:string}}[];}
const labels:Record<string,string>={include:"暂纳入候选",exclude:"已有更新研究，建议排除",uncertain:"证据不足，待核查"};
export default function FutureDirections({value}:{value:Future}){
  return <section aria-label="未来方向核查结果"><h3>未来方向与更新研究对照</h3><p>{value.notice}</p>
    {!value.directions.length?<p>所选原文证据中没有找到作者明确提出的未来工作。</p>:null}
    {value.directions.map((d,i)=><article className="sg-writing-paragraph" key={i} data-decision={d.decision}>
      <h4>{d.topic} <span className="sg-tag">{labels[d.decision]}</span></h4><p>{d.reason}</p>
      <p className="sg-mono">来源年份：{d.source_year??"尚未取得"} · 对照引文年份：{[...new Set(d.matches.map(m=>m.year).filter(y=>y!=null))].join("、")||"尚未取得"} · 检索时间：{new Date(d.searched_at).toLocaleString("zh-CN")}</p>
      <blockquote>{d.quote}</blockquote><AnchorTag anchor={d.anchor}/>
      {d.remaining_candidate?<p className="sg-note">更窄的研究设想（待查证）：{d.remaining_candidate.topic}。{d.remaining_candidate.notice}</p>:null}
      {d.error?<p className="sg-error">{d.error.message}</p>:null}
      <details><summary>本次检索结果与对照依据（{d.candidates.length}）</summary>{d.candidates.map(p=><div key={p.id}>
        <h5>{p.title}</h5><p>{p.authors.join(", ")} · {p.year??"年份待核对"} · {p.candidate_origin==='selected_library'?"所选论文原文":"公开检索结果"}</p>
        {p.id.startsWith('paper-')?<a href={`/read/${p.id}`}>查看库内原文</a>:p.source?.startsWith('https://')?<a href={p.source} target="_blank" rel="noreferrer">查看公开来源</a>:null}
        {d.matches.filter(m=>m.candidate_id===p.id).map((m,j)=><div key={j}><blockquote>{m.quote}</blockquote>{m.anchor?<AnchorTag anchor={m.anchor}/>:null}</div>)}
      </div>)}</details>
    </article>)}
  </section>;
}
