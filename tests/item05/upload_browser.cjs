// One native multi-file selection and one upload click; no mocked parser or routes.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),base=path.join(root,'data/item05-20261029'),run=process.argv[2]||'upload-browser';assert.match(run,/^[a-z0-9_-]+$/);const out=path.join(base,run);fs.mkdirSync(out);
const inputs=JSON.parse(fs.readFileSync(path.join(base,'sources.json'))).inputs;
const save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 const report={errors:[],input_count:inputs.length,upload_requests:0};page.on('pageerror',e=>report.errors.push(e.message));
 page.on('request',r=>{if(r.url().endsWith('/api/workspace/uploads')&&r.method()==='POST')report.upload_requests++;});
 try{
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  const listing=await page.request.get('http://127.0.0.1:8120/api/v1/papers');assert.equal((await listing.json()).total,0);
  await page.goto('http://127.0.0.1:3420/upload');await page.locator('input[type=file]').setInputFiles(inputs.map(r=>path.join(root,'pdf',r.filename)));
  await page.getByRole('button',{name:'上传并解析 20 篇',exact:true}).waitFor();await page.screenshot({path:path.join(out,'twenty-selected.png')});
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/workspace/uploads')&&r.request().method()==='POST',{timeout:120000}),start=Date.now();
  await page.getByRole('button',{name:'上传并解析 20 篇',exact:true}).click();const response=await pending;report.submission_status=response.status();
  const body=await response.json();save('submission.json',body);assert.equal(response.status(),202);report.task_id=body.id;save('current.json',report);
  console.log(JSON.stringify({event:'twenty-uploaded-once',task:body.id,status:response.status()}));
  let task,previous;for(let i=0;i<1800;i++){
   const r=await page.request.get('http://127.0.0.1:8120/api/v2/tasks/'+body.id);assert.equal(r.status(),200);task=await r.json();save('task-current.json',task);
   const progress=JSON.stringify(task.progress);if(progress!==previous){console.log(JSON.stringify({event:'progress',seconds:(Date.now()-start)/1000,status:task.status,progress:task.progress}));previous=progress;}
   if(!['queued','running','cancelling'].includes(task.status))break;await page.waitForTimeout(2000);
  }
  report.total_seconds=(Date.now()-start)/1000;report.task=task;
  assert.equal(task.status,'completed');assert.equal(task.result.succeeded_count,20);assert.equal(task.result.failed_count,0);assert.equal(report.upload_requests,1);
  await page.reload();await page.getByText('20 / 20',{exact:false}).first().waitFor({timeout:15000}).catch(()=>{});
  await page.screenshot({path:path.join(out,'batch-complete.png'),fullPage:true});assert.deepEqual(report.errors,[]);report.passed=true;
  console.log(JSON.stringify({event:'completed',seconds:report.total_seconds,succeeded:task.result.succeeded_count,requests:report.upload_requests}));
 }catch(e){report.passed=false;report.failure=e.stack;console.log(JSON.stringify({error:e.message}));await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{save('result.json',report);await context.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await context.close();await browser.close();}
})();
