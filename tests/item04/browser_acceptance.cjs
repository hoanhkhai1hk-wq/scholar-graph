// Actual controls in an owned temporary Chrome profile; no mock routes or forced DOM state.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item04-20261028');
const run=process.argv[2];assert.match(run,/^[a-z0-9_-]+$/);const out=path.join(base,run);fs.mkdirSync(out);
const seed=JSON.parse(fs.readFileSync(path.join(base,'seed-upload.json'))).paper_id;
const bert=JSON.parse(fs.readFileSync(path.join(base,'title-before/1-result.json'))).reading.paper.id;
const report={run,browser:'own temporary Chrome profile',errors:[],steps:[]};
const save=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2));
const print=value=>process.stdout.write(JSON.stringify(value)+'\n');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));report.version=browser.version();
 try{
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  await page.goto('http://127.0.0.1:3400/retrieval');
  await page.getByLabel('参考论文与追踪主题').selectOption(seed);
  const content=page.getByRole('button',{name:'按内容选择前十项',exact:true});await content.waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('.sg-reference-picker input').length===40);
  await content.click();
  const selected=await page.locator('.sg-reference-picker input:checked').evaluateAll(es=>es.map(e=>Number(e.closest('label').innerText.match(/\[(\d+)\]/)[1])));
  const expected=JSON.parse(fs.readFileSync(path.join(base,'reference-evaluation.json'))).after_context.top_10;
  assert.deepEqual([...selected].sort((a,b)=>a-b),[...expected].sort((a,b)=>a-b));report.content_selected=selected;
  await page.locator('.sg-reference-picker article').first().locator('summary').click();
  await page.locator('.sg-reference-picker').screenshot({path:path.join(out,'content-context.png')});
  const batchResponse=page.waitForResponse(r=>r.url().includes('/reference-tasks')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'一键获取全部 40 篇参考文献',exact:true}).click();
  const started=await batchResponse;assert.equal(started.status(),202);report.batch_task=await started.json();
  save('batch-start.json',report.batch_task);print({step:'one-click-all',task:report.batch_task.id});
  await page.getByLabel('研究主题论文').selectOption(seed);
  const recoResponse=page.waitForResponse(r=>r.url().includes('/api/workspace/recommendations?')&&r.request().method()==='GET',{timeout:120000});
  await page.getByRole('button',{name:'查看推荐',exact:true}).click();const raw=await recoResponse;assert.equal(raw.status(),200);
  const before=await raw.json();save('recommendations-before.json',before);
  const card=page.locator(`article[data-paper-id="${bert}"]`);await card.waitFor();const oldRank=Number(await card.getAttribute('data-rank'));
  report.ui_ranks={before:oldRank};
  for(const [vote,label] of [['like','有帮助'],['dislike','不相关']]){
   const response=page.waitForResponse(r=>r.url().endsWith('/recommendations/feedback')&&r.request().method()==='POST',{timeout:120000});
   await card.getByRole('button',{name:label,exact:true}).click();const event=await response;assert.equal(event.status(),200);
   const value=await event.json();save(`feedback-${vote}.json`,value);const rank=value.after.find(r=>r.paper_id===bert).rank;
   await page.waitForFunction(({id,rank})=>document.querySelector(`article[data-paper-id="${id}"]`)?.dataset.rank===String(rank),{id:bert,rank},{timeout:120000});
   await page.getByRole('status').filter({hasText:'反馈已保存：该论文从第'}).waitFor();report.ui_ranks[vote]=rank;
   await card.screenshot({path:path.join(out,`bert-${vote}.png`)});print({step:vote,rank});
  }
  assert.ok(report.ui_ranks.like<oldRank);assert.ok(report.ui_ranks.dislike>report.ui_ranks.like);
  await page.reload();await page.getByLabel('研究主题论文').selectOption(seed);
  await page.getByRole('button',{name:'查看推荐',exact:true}).click();await card.waitFor();
  await page.waitForFunction(id=>document.querySelector(`article[data-paper-id="${id}"] button[aria-pressed="true"]`)?.textContent==='不相关',bert);
  report.after_refresh={rank:Number(await card.getAttribute('data-rank')),dislike_pressed:await card.getByRole('button',{name:'不相关',exact:true}).getAttribute('aria-pressed')};
  assert.equal(report.after_refresh.rank,report.ui_ranks.dislike);assert.equal(report.after_refresh.dislike_pressed,'true');
  await card.screenshot({path:path.join(out,'bert-refresh.png')});
  // Poll the real task read-only; its creation above was the single native button click.
  let finalTask;for(let i=0;i<300;i++){
   const r=await page.request.get('http://127.0.0.1:8100/api/v2/tasks/'+report.batch_task.id);assert.equal(r.status(),200);finalTask=await r.json();save('batch-current.json',finalTask);
   if(!['queued','running','cancelling'].includes(finalTask.status))break;await page.waitForTimeout(1000);
  }
  assert.ok(['completed','partial'].includes(finalTask.status));assert.equal(finalTask.progress.completed_units,40);
  report.batch_final={status:finalTask.status,...Object.fromEntries(Object.entries(finalTask.result).filter(([k])=>k.endsWith('_count')))};
  await page.reload();const details=page.locator('.sg-section').filter({has:page.getByRole('heading',{name:'任务进度',exact:true})}).last();
  await details.locator('summary').filter({hasText:'逐项结果：'}).waitFor();await details.screenshot({path:path.join(out,'batch-final.png')});
  report.passed=true;assert.deepEqual(report.errors,[]);print({passed:true,ranks:report.ui_ranks,refresh:report.after_refresh,batch:report.batch_final});
 }catch(e){report.passed=false;report.failure=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});print({passed:false,error:e.message});process.exitCode=1;}
 finally{save('result.json',report);await context.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await context.close();await browser.close();}
})();
