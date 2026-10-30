const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item08-20261029'),run=process.argv[2],out=path.join(base,run);fs.mkdirSync(out);
const pid=JSON.parse(fs.readFileSync(path.join(base,'samples.json'))).find(p=>p.page_count===541).id;
(async()=>{for(let i=0;i<60;i++){try{const r=await fetch('http://127.0.0.1:8200/api/v2/system');if(r.ok)break;}catch{}await new Promise(r=>setTimeout(r,500));}const b=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),ctx=await b.newContext({viewport:{width:1440,height:900}}),p=await ctx.newPage(),report={paper_id:pid,errors:[],samples:[]};p.on('pageerror',e=>report.errors.push(e.message));
for(let attempt=0;attempt<3;attempt++){
 await fetch('http://127.0.0.1:8200/__item08/requests',{method:'POST'});let t=Date.now();await p.goto('http://127.0.0.1:3520/read/'+pid+'?page=1',{waitUntil:'domcontentloaded'});await p.locator('[data-page="1"][data-rendered=true]').waitFor({timeout:120000});const first=Date.now()-t;await p.waitForTimeout(300);const requests=await fetch('http://127.0.0.1:8200/__item08/requests').then(r=>r.json());const rows=[];
 for(const number of [300,541]){t=Date.now();await p.getByLabel('跳转页码').fill(String(number));await p.getByRole('button',{name:'前往',exact:true}).click();await p.locator(`[data-page="${number}"][data-rendered=true]`).waitFor({timeout:60000});await p.waitForFunction(n=>document.querySelector('.sg-layout__bar')?.textContent.includes(`当前第 ${n} 页`),number);rows.push({page:number,rendered_ms:Date.now()-t});}
 report.samples.push({attempt,first_render_ms:first,initial_api_requests:requests.filter(r=>r.path.includes(pid)),jumps:rows});fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
 if(attempt===0)await p.screenshot({path:path.join(out,'last-page.png')});
 // Clear the prior physical position for a repeat of the same first-page scenario.
 await p.evaluate(pid=>localStorage.removeItem('sg.reading.'+pid),pid);
}report.passed=!report.errors.length;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await b.close();console.log(JSON.stringify(report));if(!report.passed)process.exitCode=1;})().catch(e=>{console.error(e);process.exitCode=1});
