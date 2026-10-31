// Live UI verification plus separately labelled state simulations.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const mode=process.argv[2],base=path.resolve(__dirname,'../../data/tracking-fix-20261031'),out=path.join(base,'browser-'+(process.argv[3]||mode));fs.mkdirSync(out,{recursive:true});
let activeBrowser;
(async()=>{
 const status=await fetch('http://127.0.0.1:8100/api/v2/tracking/status').then(r=>r.json());
 const b=activeBrowser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),report={cases:[],errors:[]};
 async function open(width,simulator){
  const ctx=await b.newContext({viewport:{width,height:900},locale:'zh-CN',timezoneId:'Asia/Shanghai'});if(simulator)await ctx.route('**/api/workspace/tracking/status',route=>route.fulfill({json:simulator()}));
  const p=await ctx.newPage();p.on('pageerror',e=>report.errors.push(e.message));await p.goto('http://127.0.0.1:3400/retrieval');
  await p.getByText('高级检索、手动追踪与兼容接口诊断',{exact:true}).click();
  const outer=p.getByRole('heading',{name:'arXiv 定期追踪',exact:true}).locator('../..');
  const region=mode==='before'?outer:p.getByRole('region',{name:'arXiv追踪运行状态'});
  await region.getByRole('button',{name:'刷新状态',exact:true}).waitFor();await region.scrollIntoViewIfNeeded();
  await p.waitForTimeout(600);return {ctx,p,region,outer};
 }
 for(const width of mode==='before'?[1440]:[1440,390]){
  const {ctx,p,region,outer}=await open(width);const text=await region.innerText();
  const row={kind:'real_saved_run',width,run_status:status.latest_run.status,query_failures:status.latest_run.query_failed_count,
   shows_no_new:await region.getByText('本次没有新增论文',{exact:true}).count()>0,body_width:await p.evaluate(()=>document.documentElement.scrollWidth),text};
  if(mode==='after'){
   assert.ok(text.includes('查询失败'));
   const count=region.locator('dt').filter({hasText:'查询失败'}).locator('xpath=following-sibling::dd[1]');row.rendered_query_failures=parseInt(await count.innerText());
   // The user can start another real task during this probe. Assert invariants,
   // not that the mutable latest_run must still be the earlier partial run.
   row.running=await region.getByRole('button',{name:'正在追踪…',exact:true}).count()>0;
   if(row.running||row.rendered_query_failures>0)assert.equal(row.shows_no_new,false);
   assert.ok(row.body_width<=width+2);const main=p.getByRole('region',{name:'最近追踪记录',exact:true});row.main_grouped_alerts=await main.getByRole('alert').count();assert.ok(row.main_grouped_alerts<=1);
   await main.screenshot({path:path.join(out,'main-'+width+'.png')});
  }
  await outer.screenshot({path:path.join(out,'real-'+width+'.png')});report.cases.push(row);await ctx.close();
 }
 if(mode==='after'){
  function scenario(name){
   const v=structuredClone(status),r=v.latest_run;r.status=name;r.max_imports=0;r.phase=name==='running'?'querying':'finished';
   const error={error_code:'UPSTREAM_ERROR',message:'arXiv 请求等待超时，尚未取得结果；请稍后重试。',details:{reason:'UPSTREAM_TIMEOUT'}};
   r.queries=Array.from({length:3},(_,i)=>({query:`UI-only-test-${i+1}`,returned_count:0,error:name==='completed'||i===0?null:error}));
   r.query_total_count=name==='running'?10:3;r.query_failed_count=name==='completed'?0:2;r.query_succeeded_count=name==='completed'?3:1;
   r.errors=name==='completed'?[]:[error,error];
   r.candidate_count=0;r.discovered_count=0;r.imported_count=0;r.duplicate_count=0;r.failed_count=0;r.duration_seconds=name==='running'?null:20.74;r.finished_at=name==='running'?null:new Date().toISOString();return v;
  }
  for(const name of ['running','failed','partial','completed']){
   const {ctx,p,region}=await open(390,()=>scenario(name));const noNew=await region.getByText('本次没有新增论文',{exact:true}).count()>0;
   assert.equal(noNew,name==='completed');assert.equal(await region.getByRole('button').first().isDisabled(),name==='running');
   assert.equal(await region.getByRole('alert').count()>0,name!=='completed');report.cases.push({kind:'UI_state_simulation_only',status:name,no_new:noNew});
   const main=p.getByRole('region',{name:'最近追踪记录',exact:true});assert.equal(await main.getByRole('alert').count(),name==='completed'?0:1);
   if(name!=='completed')assert.ok((await main.innerText()).includes('共 2 条'));
   await main.screenshot({path:path.join(out,'main-state-'+name+'.png')});
   await region.screenshot({path:path.join(out,'state-'+name+'.png')});await ctx.close();
  }
  let reads=0;const {ctx,p,region}=await open(1440,()=>scenario(++reads<=2?'running':'failed'));
  await region.getByText('追踪失败',{exact:true}).waitFor({timeout:15000});assert.equal(await region.getByText('本次没有新增论文',{exact:true}).count(),0);
  report.cases.push({kind:'UI_poll_simulation_only',automatic_transition:'running -> failed',status_reads:reads});await ctx.close();
 }
 report.passed=!report.errors.length;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await b.close();console.log(JSON.stringify({passed:report.passed,cases:report.cases.length}));
})().catch(async e=>{console.error(e);if(activeBrowser)await activeBrowser.close();process.exitCode=1});
