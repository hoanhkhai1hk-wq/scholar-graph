// Own temporary browser/profile. Never opens the user's browser profile.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const root=path.join(__dirname,'../../data/item03-20261028');
const run=process.argv[2]||'native-final';assert.match(run,/^[a-zA-Z0-9_-]+$/);
const runDir=path.join(root,run);fs.mkdirSync(runDir);
const shots=path.join(__dirname,'../../test-records/item03-20261028/screenshots');
const pid='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697';
async function measure(page,input){return {input,columns:await page.locator('.sg-bilingual__scroll').evaluateAll(es=>es.map(e=>({top:e.scrollTop,max:e.scrollHeight-e.clientHeight,rows:[...e.querySelectorAll('[data-chunk-id]')].map(row=>({id:row.dataset.chunkId,top:row.getBoundingClientRect().top-e.getBoundingClientRect().top-e.clientTop+e.scrollTop}))})))};}
async function drag(page,index,fraction){
 const el=page.locator('.sg-bilingual__scroll').nth(index);await el.scrollIntoViewIfNeeded();
 const r=await el.evaluate(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.offsetWidth,h:e.clientHeight,total:e.scrollHeight,top:e.scrollTop,sw:e.offsetWidth-e.clientWidth}));
 const thumb=Math.max(30,r.h*r.h/r.total),travel=r.h-thumb,x=r.x+r.w-r.sw/2;
 await page.mouse.move(x,r.y+1+r.top/(r.total-r.h)*travel+thumb/2);await page.mouse.down();
 await page.mouse.move(x,r.y+1+fraction*travel+thumb/2,{steps:20});await page.mouse.up();await page.waitForTimeout(150);
 const value=await measure(page,`native ${index?'Chinese':'English'} scrollbar thumb drag; default scrollbar-hiding flag removed`);
 assert.ok(Math.abs(value.columns[index].top-r.top)>20,'Drag did not move the source column');
 return value;
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',ignoreDefaultArgs:['--hide-scrollbars']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});const page=await context.newPage();
 const report={browser_version:browser.version(),viewport:{width:1280,height:900},errors:[]};
 page.on('pageerror',error=>report.errors.push(error.message));
 try{
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  await page.goto(`http://127.0.0.1:3380/read/${pid}?page=1`);
  await page.getByRole('tab',{name:'双语与翻译'}).click();
  await page.getByLabel('翻译范围').selectOption('full');await page.getByRole('button',{name:'开始翻译',exact:true}).click();
  await page.locator('.sg-bilingual__scroll').first().waitFor({state:'visible',timeout:30000});
  const left=await drag(page,0,.45);
  const right=await drag(page,1,.25);
  for(const name of ['left','right']){
   const file=path.join(root,`sync-${name}-after-drag-final.json`),backup=path.join(root,`sync-${name}-drag-attempt-hidden-scrollbars.json`);
   if(fs.existsSync(file)&&!fs.existsSync(backup))fs.copyFileSync(file,backup);
   const data=JSON.stringify(name==='left'?left:right,null,2);
   fs.writeFileSync(path.join(runDir,`sync-${name}-after-drag-final.json`),data);fs.writeFileSync(file,data);
  }
  report.passed=true;report.left=left.columns.map(c=>({top:c.top,max:c.max}));report.right=right.columns.map(c=>({top:c.top,max:c.max}));
  fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,`${run}-bilingual-native-drag.png`)});
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'导出译文',exact:true}).click()]);
  await download.saveAs(path.join(runDir,'browser-export.md'));report.exported_filename=download.suggestedFilename();
  await page.reload();await page.getByRole('tab',{name:'双语与翻译'}).click();
  await page.locator('.sg-bilingual__scroll').first().waitFor({state:'visible',timeout:15000});
  report.refreshed_translation_restored=await page.getByRole('heading',{name:'已校验译文 · 共 175 段'}).isVisible();
  await page.getByLabel('翻译范围').selectOption('abstract');await page.getByRole('button',{name:'开始翻译',exact:true}).click();
  await page.getByRole('heading',{name:'已校验译文 · 共 1 段',exact:true}).waitFor({state:'visible',timeout:30000});
  const references=await page.evaluate(p=>({full:localStorage.getItem(`sg.translation.${p}.zh.full`),abstract:localStorage.getItem(`sg.translation.${p}.zh.abstract`)}),pid);
  assert.ok(references.full && references.abstract && references.full!==references.abstract);
  await page.getByLabel('翻译方向').selectOption('en');await page.getByLabel('翻译范围').selectOption('full');await page.getByRole('button',{name:'开始翻译',exact:true}).click();
  await page.getByRole('heading',{name:'已校验译文 · 共 175 段',exact:true}).waitFor({state:'visible',timeout:180000});
  const englishId=await page.evaluate(p=>localStorage.getItem(`sg.translation.${p}`),pid);
  const englishTask=await (await page.request.get(`http://127.0.0.1:3380/api/workspace/tasks/${englishId}`)).json();
  const fullTask=await (await page.request.get(`http://127.0.0.1:3380/api/workspace/tasks/${references.full}`)).json();
  const chineseById=new Map(fullTask.result.translation.segments.map(s=>[s.source_chunk_id,s.translated_text]));
  assert.equal(englishTask.result.translation.segments.length,175);
  assert.ok(englishTask.result.translation.segments.every(s=>s.source_text===chineseById.get(s.source_chunk_id)));
  report.scope_switch={chinese_full_task:references.full,chinese_abstract_task:references.abstract,english_full_task:englishId,english_segments:175,source_matches_full_chinese_by_every_chunk:true};
 }catch(error){report.passed=false;report.failure=error.message;await page.screenshot({path:path.join(runDir,'native-drag-failure.png')});}
 finally{await context.tracing.stop({path:path.join(runDir,'native-scroll-trace.zip')});await browser.close();fs.writeFileSync(path.join(runDir,'native-scroll-result.json'),JSON.stringify(report,null,2));}
 console.log(JSON.stringify(report));process.exitCode=report.passed?0:1;
})().catch(error=>{console.error(error.message);process.exitCode=1;});
