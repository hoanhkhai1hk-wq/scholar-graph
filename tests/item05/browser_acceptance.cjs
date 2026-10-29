// Actual graph, task controls, model results and navigation in an owned Chrome profile.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item05-20261029'),run=process.argv[2];assert.match(run,/^[a-z0-9_-]+$/);const out=path.join(base,run);fs.mkdirSync(out);
const save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2));
const inputs=JSON.parse(fs.readFileSync(path.join(base,'upload-twenty/result.json'))).task.result.succeeded,ids=inputs.map(x=>x.paper_id);
const report={errors:[],steps:[]};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));report.browser=browser.version();
 async function graph(name){
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/workspace/graph/rebuild')&&r.request().method()==='POST',{timeout:120000}),start=Date.now();
  await page.getByRole('button',{name:'生成图谱（已选 20）',exact:true}).click();const r=await pending;assert.equal(r.status(),200);const g=await r.json();save(name+'-response.json',g);
  await page.locator('.sg-graph__canvas[data-node-count="20"]').waitFor({timeout:30000});report[name+'_seconds']=(Date.now()-start)/1000;
  const actual=await page.locator('.sg-graph__canvas').evaluate(el=>{
   const cy=el._cyreg.cy;return {nodes:cy.nodes().map(n=>({id:n.id(),position:n.renderedPosition()})),edges:cy.edges().map(e=>({from:e.source().id(),to:e.target().id()})),zoom:cy.zoom(),layout_ms:Number(el.dataset.layoutMs),size:{width:el.clientWidth,height:el.clientHeight}};
  });
  assert.deepEqual(actual.nodes.map(n=>n.id).sort(),[...ids].sort());
  const pairs=[...new Set(g.edges.filter(e=>e.status==='verified').map(e=>e.from_paper_id+'->'+e.to_paper_id))].sort();
  assert.deepEqual(actual.edges.map(e=>e.from+'->'+e.to).sort(),pairs);assert.ok(actual.nodes.every(n=>n.position.x>=0&&n.position.x<=actual.size.width&&n.position.y>=0&&n.position.y<=actual.size.height));
  save(name+'-canvas.json',actual);report.graph={nodes:actual.nodes.length,edges:actual.edges.length,isolated:g.layers.isolated.length,layout_ms:actual.layout_ms};
  for(const filename of ['1706.03762v7.pdf','2412.19437v1.pdf','2501.12948v2.pdf']){
   const pid=inputs.find(x=>x.filename===filename).paper_id,node=g.nodes.find(n=>n.paper_id===pid),row=page.locator('tr').filter({has:page.locator(`a[href="/read/${pid}"]`)}).first();
   assert.match(await row.innerText(),new RegExp(node.pagerank.toFixed(6).replace('.','\\.')));
  }
  await page.locator('.sg-graph').screenshot({path:path.join(out,name+'.png')});return g;
 }
 async function generate(kind,buttonName){
  const pending=page.waitForResponse(r=>r.url().endsWith('/writing/tasks')&&r.request().method()==='POST'),start=Date.now();
  await page.getByRole('button',{name:buttonName,exact:true}).click();const r=await pending;assert.equal(r.status(),202);
  const body=r.request().postDataJSON();assert.deepEqual([...body.paper_ids].sort(),[...ids].sort());const task=await r.json();save(kind+'-submitted.json',task);
  let last;for(let i=0;i<600;i++){
   const res=await page.request.get('http://127.0.0.1:8120/api/v2/tasks/'+task.id);assert.equal(res.status(),200);last=await res.json();save(kind+'-task.json',last);
   if(!['queued','running','cancelling'].includes(last.status))break;await page.waitForTimeout(2000);
  }
  assert.equal(last.status,'completed',JSON.stringify(last.error));report[kind]={seconds:(Date.now()-start)/1000,id:task.id,model_calls:last.result.metadata.model_calls.length};
  console.log(JSON.stringify({event:kind,...report[kind]}));return last;
 }
 try{
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  for(let i=0;i<90;i++){
   try{const r=await page.request.get('http://127.0.0.1:8120/api/v2/system',{timeout:2000});if(r.status()===200)break;}catch{}
   await page.waitForTimeout(500);
  }
  await page.goto('http://127.0.0.1:3420/graph');const checks=page.locator('.sg-picker input[type=checkbox]');assert.equal(await checks.count(),20);
  await page.getByRole('button',{name:'全选这 20 篇论文',exact:true}).click();assert.equal(await page.locator('.sg-picker input:checked').count(),20);const g=await graph('graph-first');
  const before=await page.locator('.sg-graph__canvas').evaluate(el=>el._cyreg.cy.zoom());await page.getByRole('button',{name:'放大',exact:true}).click();
  assert.ok(await page.locator('.sg-graph__canvas').evaluate(el=>el._cyreg.cy.zoom())>before);await page.getByRole('button',{name:'适应窗口',exact:true}).click();report.zoom_controls_work=true;
  await page.getByRole('button',{name:'依据当前图谱生成综述与未来方向',exact:true}).click();
  const review=await generate('review','生成图谱综述');assert.ok(review.result.document.references.length>0);assert.ok(review.result.document.references.every(r=>ids.includes(r.paper_id)));
  await page.getByRole('article',{name:'图谱综述结果'}).waitFor();report.review.reference_count=review.result.document.references.length;
  await page.getByRole('article',{name:'图谱综述结果'}).screenshot({path:path.join(out,'review.png')});
  const future=await generate('future','核查未来方向');assert.ok(future.result.future.directions.length>=2);
  for(const d of future.result.future.directions){assert.ok(ids.includes(d.anchor.paper_id));if(d.decision==='exclude')assert.ok(d.date_check.strictly_later);}
  report.future.decisions=future.result.future.directions.map(d=>d.decision);
  await page.getByRole('region',{name:'未来方向核查结果'}).waitFor().catch(()=>page.locator('[aria-label="未来方向核查结果"]').waitFor());
  await page.locator('[aria-label="未来方向核查结果"]').screenshot({path:path.join(out,'future.png')});
  await page.reload();await page.getByRole('button',{name:'生成图谱（已选 20）',exact:true}).waitFor();await graph('graph-refresh');
  await page.getByRole('button',{name:'依据当前图谱生成综述与未来方向',exact:true}).click();await page.getByRole('article',{name:'图谱综述结果'}).waitFor();
  await page.locator('[aria-label="未来方向核查结果"]').waitFor();report.scope_and_both_results_restored=true;
  for(const [width,height] of [[1440,900],[1366,768],[1024,768],[390,844]]){
   await page.setViewportSize({width,height});
   await page.waitForFunction(()=>{const el=document.querySelector('.sg-graph__canvas'),cy=el?._cyreg?.cy;return cy&&cy.nodes().every(n=>{const p=n.renderedPosition();return p.x>=0&&p.x<=el.clientWidth&&p.y>=0&&p.y<=el.clientHeight;});},{},{timeout:10000});
   const value=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
   report['layout_'+width]=value;assert.ok(value.document<=value.viewport+1,JSON.stringify(value));await page.locator('.sg-graph').screenshot({path:path.join(out,'graph-'+width+'.png')});
  }
  await page.setViewportSize({width:1440,height:900});const canvas=page.locator('.sg-graph__canvas');await canvas.scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>{const el=document.querySelector('.sg-graph__canvas'),cy=el?._cyreg?.cy;return cy&&cy.nodes().every(n=>{const p=n.renderedPosition();return p.x>=0&&p.x<=el.clientWidth&&p.y>=0&&p.y<=el.clientHeight;});});
  const diagnostics=page.waitForResponse(r=>r.url().includes('/api/workspace/graph?')&&r.request().method()==='GET');
  await page.getByText('诊断信息与原始图谱',{exact:true}).click();const proof=await diagnostics;assert.equal(proof.status(),200);const full=await proof.json();assert.equal(full.nodes.length,20);assert.equal(full.edges.length,303);report.full_diagnostics_loaded=true;
  await page.getByText('诊断信息与原始图谱',{exact:true}).click();await canvas.scrollIntoViewIfNeeded();
  const pid=inputs.find(x=>x.filename==='1706.03762v7.pdf').paper_id,pos=await canvas.evaluate((el,id)=>el._cyreg.cy.getElementById(id).renderedPosition(),pid),box=await canvas.boundingBox();
  await page.mouse.click(box.x+pos.x,box.y+pos.y);await page.waitForURL('**/papers/'+pid);report.node_navigation=page.url();assert.deepEqual(report.errors,[]);report.passed=true;
  console.log(JSON.stringify({passed:true,graph:report.graph,restored:report.scope_and_both_results_restored,review:report.review,future:report.future}));
 }catch(e){report.passed=false;report.failure=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});console.log(JSON.stringify({passed:false,error:e.message}));process.exitCode=1;}
 finally{save('result.json',report);await context.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await context.close();await browser.close();}
})();
