const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'../../data/item04-20261028'),run=process.argv[2];assert.match(run,/^[a-z0-9_-]+$/);const out=path.join(root,run);fs.mkdirSync(out);
const seed=JSON.parse(fs.readFileSync(path.join(root,'seed-upload.json'))).paper_id;
const reformer=JSON.parse(fs.readFileSync(path.join(root,'title-before/2-result.json'))).reading.paper.id;
const report={errors:[]},save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  await page.goto('http://127.0.0.1:3400/retrieval');await page.getByLabel('论文完整标题').fill('Reformer: The Efficient Transformer');
  const taskResponse=page.waitForResponse(r=>r.url().endsWith('/acquisition/tasks')&&r.request().method()==='POST');await page.getByRole('button',{name:'查找、下载并入库',exact:true}).click();
  const r=await taskResponse;assert.equal(r.status(),202);const task=await r.json();let done;
  for(let i=0;i<120;i++){done=await (await page.request.get('http://127.0.0.1:8100/api/v2/tasks/'+task.id)).json();if(!['queued','running'].includes(done.status))break;await page.waitForTimeout(500);}
  assert.equal(done.status,'completed');assert.equal(done.result.duplicate_count,1);save('title-task.json',done);report.title={status:done.status,duplicate_count:1,task_id:task.id};
  await page.getByText('逐项结果：成功或已存在 1 篇，失败 0 项（展开查看）',{exact:true}).click();await page.getByText('库中已有，已跳过下载。',{exact:true}).waitFor();
  await page.locator('section').filter({has:page.getByRole('heading',{name:'任务进度',exact:true})}).last().screenshot({path:path.join(out,'title-duplicate-ui.png')});
  await page.getByLabel('参考论文与追踪主题').selectOption(seed);await page.waitForFunction(()=>document.querySelectorAll('.sg-reference-picker input').length===40);
  await page.getByRole('button',{name:'按引用次数选择前十项',exact:true}).click();report.frequency_selected=await page.locator('.sg-reference-picker input:checked').evaluateAll(es=>es.map(e=>Number(e.closest('label').innerText.match(/\[(\d+)\]/)[1])));
  await page.getByLabel('执行频率').selectOption('weekly');const scheduleResponse=page.waitForResponse(r=>r.url().endsWith('/tracking/schedule')&&r.request().method()==='POST');await page.getByRole('button',{name:'保存计划',exact:true}).click();const schedule=await scheduleResponse;assert.equal(schedule.status(),200);report.weekly=await schedule.json();assert.equal(report.weekly.runtime.interval_seconds,604800);save('weekly-schedule.json',report.weekly);
  await page.getByLabel('执行频率').selectOption('daily');const restoredResponse=page.waitForResponse(r=>r.url().endsWith('/tracking/schedule')&&r.request().method()==='POST');await page.getByRole('button',{name:'保存计划',exact:true}).click();report.daily_restored=await (await restoredResponse).json();assert.equal(report.daily_restored.runtime.interval_seconds,86400);
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]){await page.setViewportSize(viewport);const geometry=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert.ok(geometry.scrollWidth<=geometry.width+1);report['layout_'+viewport.width]=geometry;await page.screenshot({path:path.join(out,`discovery-${viewport.width}.png`)});}
  await page.setViewportSize({width:1440,height:900});await page.getByLabel('研究主题论文').selectOption(seed);
  const reco=page.waitForResponse(r=>r.url().includes('/api/workspace/recommendations?'),{timeout:120000});await page.getByRole('button',{name:'查看推荐',exact:true}).click();const values=await (await reco).json();const item=values.items.find(i=>i.paper.id===reformer);assert.ok(item.code_links.length);assert.equal(item.code_priority_bonus,10);save('reformer-recommendation.json',item);
  const card=page.locator(`article[data-paper-id="${reformer}"]`);await card.waitFor();const p=card.locator('p').filter({has:page.getByRole('link',{name:'原文代码链接',exact:true})}).first();const anchor=p.locator('a.sg-anchor-inline');const href=await anchor.getAttribute('href');assert.ok(href.includes('page=8'));
  await anchor.click();await page.locator('.sg-pdfpage__hit').first().waitFor({timeout:60000});report.code_anchor={href,current_url:page.url(),hit_count:await page.locator('.sg-pdfpage__hit').count()};await page.screenshot({path:path.join(out,'code-anchor-page8.png')});
  await page.goto('http://127.0.0.1:3410/retrieval');await page.getByLabel('参考论文与追踪主题').selectOption(seed);
  const faultResponse=page.waitForResponse(r=>r.url().endsWith('/tracking/tasks')&&r.request().method()==='POST');await page.getByRole('button',{name:'立即发现新论文',exact:true}).click();report.fault_task=await (await faultResponse).json();
  await page.getByText('查询失败 2 条',{exact:false}).first().waitFor({timeout:60000});await page.getByRole('button',{name:'重试任务',exact:true}).waitFor();
  const monitor=page.locator('section').filter({has:page.getByRole('heading',{name:'任务进度',exact:true})}).last();assert.ok((await monitor.innerText()).includes('未完成'));await monitor.screenshot({path:path.join(out,'failure-release-ui.png')});
  report.fault_ui={failed:await monitor.innerText(),retry_visible:true};assert.deepEqual(report.errors,[]);report.passed=true;process.stdout.write(JSON.stringify({passed:true,title:report.title,code_anchor:report.code_anchor,layouts:[report.layout_1440,report.layout_390],failure_retry:true})+'\n');
 }catch(e){report.passed=false;report.failure=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});process.stdout.write(JSON.stringify({passed:false,error:e.message})+'\n');process.exitCode=1;}
 finally{save('result.json',report);await context.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await context.close();await browser.close();}
})();
