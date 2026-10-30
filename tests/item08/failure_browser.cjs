// Deliberate failures from actual backend tasks, never fake success UI payloads.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');const base=path.resolve(__dirname,'../../data/item08-20261029'),run=process.argv[2],expect=process.argv[3],out=path.join(base,run);fs.mkdirSync(out);
const pid='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697';
(async()=>{const data=JSON.parse(fs.readFileSync(path.join(base,'failures-seeded/report.json'))),b=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),report={expected:expect,cases:[],errors:[]};
for(const name of ['translation','tracking','fetch']){
 const ctx=await b.newContext({viewport:{width:1440,height:900}});await ctx.addInitScript(({name,id,pid})=>{localStorage.setItem(name==='translation'?'sg.translation.'+pid:'sg.acquisition.task',id);},{name,id:data.tasks[name].id,pid});const p=await ctx.newPage();p.on('pageerror',e=>report.errors.push(e.message));await p.goto('http://127.0.0.1:3530'+(name==='translation'?'/read/'+pid:'/retrieval'));
 if(name==='translation')await p.getByRole('tab',{name:'双语与翻译'}).click();
 const task=p.getByRole('heading',{name:'任务进度',exact:true}).locator('..').locator('..');await task.getByText('未完成',{exact:true}).waitFor({timeout:30000});await task.scrollIntoViewIfNeeded();const row={name,status:await task.innerText(),alerts:await p.getByRole('alert').allTextContents()};
 if(name==='translation'){
   const button=p.getByRole('button',{name:'导出译文',exact:true});await button.waitFor();row.exportDisabled=await button.isDisabled();row.incompleteVisible=await p.getByRole('heading',{name:/译文尚未完成/}).count()>0;row.visibleValidationCause=(await p.locator('body').innerText()).includes('段落缺失');
   assert.equal(row.exportDisabled,expect==='after');
   if(expect==='after'){assert.ok(row.incompleteVisible&&row.visibleValidationCause);await task.getByRole('button',{name:'重试任务',exact:true}).click();await p.waitForFunction(old=>localStorage.getItem('sg.translation.'+old.pid)!==old.id,{pid,id:data.tasks[name].id});row.retryCreatedNewTask=true;await task.getByText('未完成',{exact:true}).waitFor({timeout:30000});}
 }else{assert.ok(row.status.includes('未完成'));assert.ok(row.alerts.length>0,'Failure reason must be visible');}
 await p.screenshot({path:path.join(out,name+'.png')});report.cases.push(row);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await ctx.close();
}report.passed=!report.errors.length;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await b.close();console.log(JSON.stringify({passed:report.passed,cases:report.cases.length}));})().catch(e=>{console.error(e);process.exitCode=1});
