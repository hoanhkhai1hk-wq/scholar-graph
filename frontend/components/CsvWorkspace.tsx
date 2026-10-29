"use client";
import { useState } from "react";
import { workspaceRequest } from "@/lib/workspace";
interface Preview { columns:string[];rows:string[][];total_rows:number;csv_ref:string; }
interface Result {
  kind:string;image:string|null;radar_note:string|null;
  data_table:{columns:string[];rows:{row_number:number;label:string;values:Record<string,number>}[]};
  captions:{text:string;csv_anchors:{row_number:number;column_name:string}[]}[];
  numeric_checks:{value:number;csv_anchor:{row_number:number;column_name:string}}[];
}
const LABELS:Record<string,string>={table:"数值表格",line:"折线图",bar:"柱状图",radar3d:"三维雷达图"};
export default function CsvWorkspace(){
  const [file,setFile]=useState<File|null>(null),[preview,setPreview]=useState<Preview|null>(null),[result,setResult]=useState<Result|null>(null);
  const [columns,setColumns]=useState<string[]>([]),[label,setLabel]=useState(""),[kind,setKind]=useState("bar"),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  async function choose(next:File|null){
    setFile(next);setPreview(null);setResult(null);setColumns([]);setLabel("");setError("");if(!next)return;
    setBusy(true);try{const form=new FormData();form.append("file",next);setPreview(await workspaceRequest<Preview>("/charts/preview",{method:"POST",body:form}));}
    catch(cause){setError(cause instanceof Error?cause.message:"CSV预览失败。");}finally{setBusy(false);}
  }
  async function generate(){
    if(!file)return;setBusy(true);setError("");setResult(null);
    try{const form=new FormData();form.append("file",file);form.append("kind",kind);form.append("columns",JSON.stringify(columns));if(label)form.append("label_column",label);
      setResult(await workspaceRequest<Result>("/charts",{method:"POST",body:form}));}
    catch(cause){setError(cause instanceof Error?cause.message:"图表未能生成。");}finally{setBusy(false);}
  }
  const condition=!columns.length?"请先选择数值列":kind==="radar3d"&&columns.length<3?"三维雷达图至少需要三个数值列":"";
  return <section className="sg-section" aria-label="CSV科研绘图">
    <h2 className="sg-section__title">数据表格与科研绘图</h2>
    <p>上传CSV后选择标签和数值列。每个结果附带趋势图注，可回溯首末值、净变化和源单元格；趋势按CSV记录顺序判断。</p>
    <input type="file" accept=".csv,text/csv" aria-label="选择 CSV 文件" onChange={e=>void choose(e.target.files?.[0]??null)} disabled={busy}/>
    {preview?<><p>共{preview.total_rows}条记录；下表预览前{preview.rows.length}条。</p>
      <div className="sg-topology-scroll"><table className="sg-table" aria-label="CSV输入预览"><thead><tr>{preview.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{preview.rows.map((row,i)=><tr key={i}>{row.map((c,j)=><td key={j}>{c}</td>)}</tr>)}</tbody></table></div>
      <div className="sg-form"><label className="sg-field">图表类型<select className="sg-input" disabled={busy} value={kind} onChange={e=>setKind(e.target.value)}>{Object.entries(LABELS).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
      <label className="sg-field">记录标签列<select className="sg-input" disabled={busy} value={label} onChange={e=>{setLabel(e.target.value);setColumns(cols=>cols.filter(c=>c!==e.target.value));}}><option value="">使用原始行号</option>{preview.columns.map(c=><option key={c}>{c}</option>)}</select></label></div>
      <fieldset disabled={busy}><legend>数值列（三维雷达图至少选三列）</legend>{preview.columns.map(c=><label className="sg-checkbox" key={c}><input type="checkbox" disabled={label===c} checked={columns.includes(c)} onChange={()=>setColumns(cols=>cols.includes(c)?cols.filter(x=>x!==c):[...cols,c])}/>{c}</label>)}</fieldset>
      <button className="sg-btn" disabled={busy||!!condition} title={condition||undefined} onClick={()=>void generate()}>{busy?"正在生成…":"生成表格或图表"}</button>{condition?<p className="sg-mono">{condition}</p>:null}
    </>:<p>选择一份CSV开始，支持UTF-8编码及最多1000条记录。</p>}
    {busy?<p role="status">正在读取源数据并计算…</p>:null}{error?<p role="alert" className="sg-error">{error}</p>:null}
    {result?<section aria-label="CSV生成结果"><h3>{LABELS[result.kind]}结果</h3>
      {result.image?<><img className="sg-chart-image" src={result.image} alt={LABELS[result.kind]+"，数值来自上传CSV"}/><a className="sg-btn sg-btn--ghost" href={result.image} download={"科研"+result.kind+".png"}>下载图片</a></>:null}
      {result.kind==="table"?<div className="sg-topology-scroll"><table className="sg-table" aria-label="生成的数值表格"><thead><tr><th>CSV行号</th>{result.data_table.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{result.data_table.rows.map(r=><tr key={r.row_number}><td>{r.row_number}</td>{result.data_table.columns.map(c=><td key={c}>{Object.prototype.hasOwnProperty.call(r.values,c)?r.values[c]:r.label}</td>)}</tr>)}</tbody></table></div>:null}
      {result.radar_note?<p className="sg-note">{result.radar_note}</p>:null}
      <h4>图注与趋势结论</h4>{result.captions.map((c,i)=><div key={i}><p className="sg-prose" data-caption>{c.text}</p><details><summary>趋势依据</summary>{c.csv_anchors.map((a,j)=><span key={j}>第{a.row_number}行 · {a.column_name}；</span>)}</details></div>)}
      <details><summary>源数据与逐单元格数值核对</summary><div className="sg-topology-scroll"><table className="sg-table"><thead><tr><th>CSV行号</th><th>列名</th><th>数值</th></tr></thead><tbody>{result.numeric_checks.map((c,i)=><tr key={i}><td>{c.csv_anchor.row_number}</td><td>{c.csv_anchor.column_name}</td><td>{c.value}</td></tr>)}</tbody></table></div></details>
    </section>:null}
  </section>;
}
