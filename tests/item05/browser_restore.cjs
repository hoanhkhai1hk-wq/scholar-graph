// Reopen actual persisted model tasks; this verifies restoration/UI, not a new model call.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item05-20261029'),run=process.argv[2];assert.match(run,/^[a-z0-9_-]+$/);const out=path.join(base,run);fs.mkdirSync(out);
const read=p=>JSON.parse(fs.readFileSync(path.join(base,p))),write=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2));
const ids=read('upload-twenty/result.json').task.result.succeeded.map(p=>p.paper_id),review=read('browser-accepted/review-task.json'),future=read(process.argv[3]||'browser-final/future-task.json');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),ctx=await browser.newContext({viewport:{width:1440,height:900}}),page=await ctx.newPage();const report={errors:[],reused_real_task_ids:{review:review.id,future:future.id},viewports:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 await ctx.addInitScript(({ids,review,future})=>{const k='sg.graph.research.'+[...ids].sort().join(',');localStorage.setItem('sg.graph.scope',JSON.stringify(ids));localStorage.setItem(k+'.review',review.id);localStorage.setItem(k+'.future',future.id);},{ids,review,future});
 async function fit(){await page.waitForFunction(()=>{const el=document.querySelector('.sg-graph__canvas'),cy=el?._cyreg?.cy;return cy&&cy.nodes().length===20&&cy.nodes().every(n=>{const p=n.renderedPosition();return p.x>=0&&p.x<=el.clientWidth&&p.y>=0&&p.y<=el.clientHeight;});},{},{timeout:15000});}
 try{
  await page.goto('http://127.0.0.1:3420/graph');const start=Date.now();await page.getByRole('button',{name:'生成图谱（已选 20）',exact:true}).click();await page.locator('.sg-graph__canvas[data-node-count="20"]').waitFor({timeout:120000});await fit();report.graph_seconds=(Date.now()-start)/1000;
  report.canvas=await page.locator('.sg-graph__canvas').evaluate(el=>({nodes:el._cyreg.cy.nodes().length,edges:el._cyreg.cy.edges().length,layout_ms:Number(el.dataset.layoutMs)}));assert.equal(report.canvas.edges,99);
  const labels=await page.locator('.sg-graph__canvas').evaluate(el=>el._cyreg.cy.nodes().map(n=>({id:n.id(),label:n.data('label'),title:n.data('fullTitle')})));
  assert.equal(new Set(labels.map(n=>n.label)).size,20);assert.ok(labels.every(n=>/^\d{2}$/.test(n.label)));
  for(const n of labels){const row=page.locator('tr').filter({has:page.locator(`a[href="/read/${n.id}"]`)}).first();assert.equal(await row.locator('td').first().innerText(),n.label);}
  const cv=page.locator('.sg-graph__canvas');await cv.scrollIntoViewIfNeeded();const point=await cv.evaluate(el=>el._cyreg.cy.nodes()[0].renderedPosition()),bounds=await cv.boundingBox();await page.mouse.move(bounds.x+point.x,bounds.y+point.y);await page.getByText(labels[0].label+' · '+labels[0].title,{exact:true}).waitFor();report.number_mapping_and_hover=true;
  await page.getByRole('button',{name:'依据当前图谱生成综述与未来方向',exact:true}).click();await page.getByRole('article',{name:'图谱综述结果'}).waitFor();await page.locator('[aria-label="未来方向核查结果"]').waitFor();
  await page.getByRole('article',{name:'图谱综述结果'}).screenshot({path:path.join(out,'review.png')});await page.locator('[aria-label="未来方向核查结果"]').screenshot({path:path.join(out,'future.png')});
  if(future.result.future.directions.some(d=>d.search_errors?.length)){report.partial_search_warning_visible=await page.locator('[aria-label="未来方向核查结果"]').getByText('部分公开检索失败；仅依据已取得的库内原文和公开结果核查，检索覆盖不完整。',{exact:true}).count();assert.ok(report.partial_search_warning_visible>0);}
  for(const [width,height] of [[1440,900],[1366,768],[1024,768],[390,844]]){
   await page.setViewportSize({width,height});await fit();await page.waitForTimeout(100);
   const v=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(v.document<=v.viewport+1,JSON.stringify(v));report.viewports.push({...v,height,all_node_centres_visible:true});await page.locator('.sg-graph').screenshot({path:path.join(out,'graph-'+width+'.png')});
  }
  await page.setViewportSize({width:1440,height:900});await fit();
  const pending=page.waitForResponse(r=>r.url().includes('/api/workspace/graph?'));await page.getByText('诊断信息与原始图谱',{exact:true}).click();const res=await pending;assert.equal(res.status(),200);const full=await res.json();assert.equal(full.edges.length,303);report.full_diagnostics_edges=full.edges.length;
  await page.getByText('诊断信息与原始图谱',{exact:true}).click();
  const anchor=page.locator('section').filter({has:page.getByRole('heading',{name:'逐条查证引用',exact:true})}).last().locator('a').first();const href=await anchor.getAttribute('href');assert.match(href,/page=\d+.*chunk=/);await anchor.click();await page.waitForURL('**/read/**');report.edge_anchor_navigation=page.url();
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.error=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{write('result.json',report);console.log(JSON.stringify(report));await ctx.close();await browser.close();}
})().catch(e=>{console.log(e.stack);process.exitCode=1;});
