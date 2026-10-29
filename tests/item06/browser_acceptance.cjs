// Real page operations and provider results. Persisted translations may use their verified cache.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item06-20261029'),out=path.join(base,process.argv[2]);fs.mkdirSync(out);
const save=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)),read=p=>JSON.parse(fs.readFileSync(path.join(base,p)));
const papers=read('selected-papers.json'),ids=papers.map(p=>p.paper_id),pid=read('chinese-paper.json').paper_id;
const idea='以Transformer为基础，结合低秩适配和人类反馈，提出有限算力下科研问答系统的验证方案。分别引用三篇所选论文的真实贡献，明确区分已有结论与待验证设想，不能捏造实验结果。';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),ctx=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true}),page=await ctx.newPage(),report={errors:[],cases:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function poll(task,name){for(let n=0;n<900;n++){const r=await page.request.get('http://127.0.0.1:8140/api/v2/tasks/'+task.id);assert.equal(r.status(),200);const t=await r.json();save(name+'-task.json',t);if(!['queued','running','cancelling'].includes(t.status))return t;await page.waitForTimeout(1000);}throw Error('Task deadline');}
 async function writing(area,kind){const pending=page.waitForResponse(r=>r.url().endsWith('/writing/tasks')&&r.request().method()==='POST'),start=Date.now();await area.getByRole('button',{name:'开始生成',exact:true}).click();const r=await pending;assert.equal(r.status(),202);const t=await poll(await r.json(),kind);assert.equal(t.status,'completed',JSON.stringify(t.error));report.cases.push({case:kind,task_id:t.id,seconds:(Date.now()-start)/1000,model_calls:t.result.metadata.model_calls.length});return t;}
 try{
  await ctx.tracing.start({screenshots:true,snapshots:true,sources:false});
  await page.goto('http://127.0.0.1:3440/writing?papers='+ids.join(',')+'&kind=outline');const area=page.locator('section').filter({has:page.getByRole('heading',{name:'研究想法与文献写作',exact:true})}).last();
  await area.getByLabel('研究想法或写作要求',{exact:true}).fill(idea);const outline=await writing(area,'outline');assert.ok(outline.result.document.references.length>0);assert.ok(outline.result.document.references.every(r=>ids.includes(r.paper_id)));
  await area.locator('article').waitFor();await area.locator('article').screenshot({path:path.join(out,'outline.png')});
  await area.getByRole('combobox').first().selectOption('topology');for(const id of ids.slice(1))await area.locator('input[value="'+id+'"]').uncheck();
  await area.getByLabel('研究想法或写作要求',{exact:true}).fill('从Attention原文提取Transformer实际方法逻辑，输出输入、嵌入、编码器、解码器和输出之间的真实依赖，不要把章节顺序当作方法。');
  const topology=await writing(area,'topology');await area.getByRole('img',{name:'论文方法拓扑',exact:true}).waitFor();await area.getByRole('img',{name:'论文方法拓扑',exact:true}).screenshot({path:path.join(out,'topology-ui.png')});
  fs.mkdirSync(path.join(out,'downloads'));
  for(const script of topology.result.topology.scripts){const title={tikz:'LaTeX TikZ 绘图代码',dot:'Graphviz 绘图代码',mermaid:'Mermaid 绘图代码',matplotlib:'Matplotlib 绘图代码'}[script.format],detail=area.locator('details').filter({has:page.getByText(title,{exact:true})});
   await detail.locator('summary').click();const pending=page.waitForEvent('download');await detail.getByRole('button',{name:'下载代码',exact:true}).click();const d=await pending,file=path.join(out,'downloads',d.suggestedFilename());await d.saveAs(file);assert.equal(fs.readFileSync(file,'utf8'),script.script);await detail.locator('summary').click();
  }report.four_scripts_downloaded=true;
  const csv=page.getByRole('region',{name:'CSV科研绘图',exact:true});await csv.getByLabel('选择 CSV 文件',{exact:true}).setInputFiles(path.join(base,'matrix-timings.csv'));
  await csv.getByRole('table',{name:'CSV输入预览',exact:true}).waitFor();await csv.getByRole('combobox').nth(1).selectOption('dimension');for(const col of ['matmul_ms','add_ms','multiply_ms'])await csv.getByLabel(col,{exact:true}).check();
  for(const kind of ['table','line','bar','radar3d']){
   await csv.getByRole('combobox').nth(0).selectOption(kind);const pending=page.waitForResponse(r=>r.url().endsWith('/api/workspace/charts')),start=Date.now();await csv.getByRole('button',{name:'生成表格或图表',exact:true}).click();const r=await pending;assert.equal(r.status(),200);const value=await r.json();save(kind+'-response.json',value);const result=csv.getByRole('region',{name:'CSV生成结果',exact:true});await result.waitFor();
   assert.equal(value.data_table.rows.length,5);assert.equal(value.numeric_checks.length,15);assert.equal(value.captions.length,3);assert.ok(value.captions.every(c=>c.text.includes('净变化')&&c.text.includes('上升')&&c.numeric_facts));
   if(kind==='table')assert.equal(await result.getByRole('table',{name:'生成的数值表格',exact:true}).locator('tbody tr').count(),5);
   else{await result.locator('img').evaluate(el=>el.decode());assert.ok(await result.locator('img').evaluate(el=>el.naturalWidth>0));fs.writeFileSync(path.join(out,kind+'.png'),Buffer.from(value.image.split(',')[1],'base64'));}
   report.cases.push({case:kind,seconds:(Date.now()-start)/1000,rows:5,source_cell_checks:15,trend_captions:3,numeric_caption_facts:9});await result.screenshot({path:path.join(out,kind+'-ui.png')});
  }
  for(const [width,height] of [[1440,900],[1366,768],[1024,768],[390,844]]){await page.setViewportSize({width,height});await page.waitForTimeout(100);const v=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));assert.ok(v.document<=v.viewport+1,JSON.stringify(v));report['layout_'+width]=v;await csv.screenshot({path:path.join(out,'csv-'+width+'.png')});}
  await page.setViewportSize({width:1440,height:900});await page.goto('http://127.0.0.1:3440/read/'+pid);await page.getByRole('tab',{name:'双语与翻译',exact:true}).click();const translation=page.locator('.sg-translate');await translation.getByRole('combobox').nth(0).selectOption('en');
  for(const scope of ['abstract','full']){await translation.getByRole('combobox').nth(1).selectOption(scope);const pending=page.waitForResponse(r=>r.url().endsWith('/translation-tasks')&&r.request().method()==='POST');await translation.getByRole('button',{name:'开始翻译',exact:true}).click();const r=await pending;assert.equal(r.status(),202);const t=await poll(await r.json(),scope+'-en');assert.equal(t.status,'completed');const m=t.result.translation.metadata;assert.ok(m.complete);report.cases.push({case:scope+'_en',segments:m.translated_segments,cache_hits:m.cache_hits,model_calls:m.model_calls.length});await translation.getByRole('heading',{name:/已校验译文/}).waitFor();await translation.screenshot({path:path.join(out,scope+'-en-ui.png')});}
  await page.reload();await page.getByRole('tab',{name:'双语与翻译',exact:true}).click();await page.locator('.sg-translate').getByRole('heading',{name:/已校验译文/}).waitFor();report.translation_restored=true;assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{save('result.json',report);console.log(JSON.stringify(report));await ctx.tracing.stop({path:path.join(out,'trace.zip')}).catch(()=>{});await ctx.close();await browser.close();}
})().catch(e=>{console.log(e.stack);process.exitCode=1;});
