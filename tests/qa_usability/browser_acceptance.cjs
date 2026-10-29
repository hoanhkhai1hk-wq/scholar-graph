// Real buttons and real model, in an owned temporary Chrome profile.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/qa-usability-20261028'),run=process.argv[2];assert.match(run,/^[a-z0-9_-]+$/);
const out=path.join(base,run);fs.mkdirSync(out);const save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2));
const old=JSON.parse(fs.readFileSync(path.join(base,'before/pair.json'))),scope=[...old.paper_ids].sort().join(',');
const reader='paper-1cb48e40e523d1994f38211edd30f92b0f01f0a25c2990bc8d84a9b684e95135';
const report={errors:[],cases:[],historical_session_reused:old.session_id,history_source:'genuine pre-fix refused server session, not a fixture or fabricated DOM'};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));report.browser=browser.version();
 try{
  await context.addInitScript(({scope,old})=>{if(!localStorage.getItem('qa-acceptance-seeded')){
   localStorage.setItem('sg.research.scope',JSON.stringify(old.paper_ids));localStorage.setItem('sg.session.'+scope,old.session_id);localStorage.setItem('qa-acceptance-seeded','true');
  }},{scope,old});
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  await page.goto('http://127.0.0.1:3400/qa');
  await page.getByRole('button',{name:'重新检索此问题',exact:true}).first().waitFor();
  const oldCount=await page.locator('.sg-chat__question').count();assert.ok(oldCount>=1);report.questions_before=oldCount;
  async function answer(name,button,expectedRefusal=false){
   const started=Date.now(),pending=page.waitForResponse(r=>r.url().endsWith('/messages/stream')&&r.request().method()==='POST',{timeout:120000});
   await button.click();const response=await pending,raw=await response.text();fs.writeFileSync(path.join(out,name+'.sse'),raw);
   assert.equal(response.status(),200);const events=raw.split(/\n\n/).map(b=>({type:b.match(/^event: (.+)$/m)?.[1],data:b.match(/^data: (.+)$/m)?.[1]}));
   const final=events.find(e=>e.type==='final');assert.ok(final,raw.slice(-600));const result=JSON.parse(final.data);assert.equal(result.refused,expectedRefusal);
   const row={name,seconds:(Date.now()-started)/1000,result};report.cases.push(row);save(name+'.json',row);
   await page.getByRole('button',{name:'发送',exact:true}).waitFor();return result;
  }
  const retried=await answer('retry-old-refusal',page.getByRole('button',{name:'重新检索此问题',exact:true}).first());
  assert.equal(new Set(retried.paragraphs.flatMap(p=>p.citations.map(c=>c.anchor.paper_id))).size,2);
  assert.equal(await page.locator('.sg-chat__question').count(),oldCount+1);report.old_refusal_retained=await page.getByRole('button',{name:'重新检索此问题',exact:true}).count()>=1;
  await page.locator('.sg-chat__answer').last().locator('summary').filter({hasText:'查看本段原文依据'}).first().click();
  await page.locator('.sg-chat__answer').last().screenshot({path:path.join(out,'qa-answer.png')});
  await page.reload();await page.locator('.sg-chat__question').nth(oldCount).waitFor();report.retry_persisted_on_refresh=true;
  const count=await page.locator('.sg-chat__question').count();await page.getByRole('button',{name:'比较共同点与区别',exact:true}).click();
  assert.equal(await page.getByRole('textbox',{name:'研究问题',exact:true}).inputValue(),'这几篇论文有哪些共同点和区别？');assert.equal(await page.locator('.sg-chat__question').count(),count);report.example_fills_without_sending=true;
  await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('他们有什么关联');
  await answer('native-screenshot-question',page.getByRole('button',{name:'发送',exact:true}));
  await page.goto('http://127.0.0.1:3400/read/'+reader+'?page=3&chunk='+reader+'-p0003-c00038');
  const assistant=page.getByRole('complementary',{name:'论文研究助手',exact:true});await assistant.waitFor();
  assert.match(await assistant.innerText(),/当前论文：Structured Attention Networks/);report.reader_scope_correct=true;
  await assistant.getByRole('button',{name:'了解创新点',exact:true}).click();
  assert.equal(await assistant.getByRole('textbox',{name:'研究问题'}).inputValue(),'这篇论文的创新点是什么？');
  const novelty=await answer('reader-novelty',assistant.getByRole('button',{name:'发送',exact:true}));
  assert.ok(novelty.paragraphs.flatMap(p=>p.citations).every(c=>c.anchor.paper_id===reader));
  await assistant.locator('summary').filter({hasText:'查看本段原文依据'}).first().click();
  const link=assistant.locator('a.sg-anchor-inline').first();report.clicked_evidence=await link.getAttribute('href');
  const expectedPage=Number(new URL(report.clicked_evidence,'http://127.0.0.1:3400').searchParams.get('page'));await link.click();
  await page.locator(`.sg-pdfpage[data-page="${expectedPage}"] .sg-pdfpage__hit`).waitFor({state:'visible',timeout:30000});
  await page.locator('.sg-layout__note').filter({hasText:`段落级定位：第 ${expectedPage} 页`}).waitFor();
  await page.waitForFunction(expected=>{
   const hit=document.querySelector(`.sg-pdfpage[data-page="${expected}"] .sg-pdfpage__hit`),root=document.querySelector('[data-document-scroll]');
   if(!hit||!root)return false;const a=hit.getBoundingClientRect(),b=root.getBoundingClientRect();return a.bottom>b.top && a.top<b.bottom;
  },expectedPage,{timeout:30000});
  assert.equal(Number(new URL(page.url()).searchParams.get('page')),expectedPage);
  report.reader_source_highlight=true;report.highlighted_page=expectedPage;
  await page.screenshot({path:path.join(out,'reader-source.png')});
  await assistant.getByRole('textbox',{name:'研究问题'}).fill('它是怎么建模结构依赖的？');
  await answer('reader-method',assistant.getByRole('button',{name:'发送',exact:true}));
  await assistant.screenshot({path:path.join(out,'reader-answer.png')});
  await page.reload();await assistant.locator('.sg-chat__question').filter({hasText:'它是怎么建模结构依赖的？'}).waitFor();report.reader_history_restored=true;
  for(const [width,height] of [[1440,900],[390,844]]){
   await page.setViewportSize({width,height});await page.goto('http://127.0.0.1:3400/qa');await page.getByRole('textbox',{name:'研究问题'}).waitFor();
   const layout=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(layout.document<=layout.viewport+1,JSON.stringify(layout));
   report['layout_'+width]=layout;await page.screenshot({path:path.join(out,'qa-'+width+'.png')});
  }
  assert.deepEqual(report.errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,cases:report.cases.map(c=>({name:c.name,seconds:c.seconds})),highlight:report.reader_source_highlight}));
 }catch(e){report.passed=false;report.failure=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});console.log(JSON.stringify({passed:false,error:e.message}));process.exitCode=1;}
 finally{save('result.json',report);await context.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await context.close();await browser.close();}
})();
