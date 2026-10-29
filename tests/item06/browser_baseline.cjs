const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item06-20261029'),out=path.join(base,process.argv[2]||'browser-before');fs.mkdirSync(out);
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),page=await browser.newPage({viewport:{width:1440,height:900}});
 try{await page.goto('http://127.0.0.1:3440/writing');const area=page.locator('section').filter({has:page.getByRole('heading',{name:'数据表格与科研绘图',exact:true})}).last();
 const previewResponse=page.waitForResponse(r=>r.url().includes('/charts/preview'));await area.getByLabel('选择 CSV 文件',{exact:true}).setInputFiles(path.join(base,'matrix-timings.csv'));const preview=await previewResponse;fs.writeFileSync(path.join(out,'preview.json'),JSON.stringify({status:preview.status(),body:await preview.text()},null,2));await area.screenshot({path:path.join(out,'after-upload.png')});await area.locator('select').nth(0).selectOption('table');await area.locator('select').nth(1).selectOption('dimension');
 for(const col of ['matmul_ms','add_ms','multiply_ms'])await area.getByLabel(col,{exact:true}).check();
 const pending=page.waitForResponse(r=>r.url().endsWith('/api/workspace/charts'));await area.getByRole('button',{name:'生成表格或图表',exact:true}).click();const r=await pending;assert.equal(r.status(),200);const v=await r.json();
 await area.getByRole('heading',{name:'生成结果',exact:true}).waitFor();const report={backend_data_rows:v.data_table.rows.length,visible_generated_table_count:await area.getByRole('table',{name:'生成的数值表格',exact:true}).count(),caption_numeric_facts:v.captions.filter(c=>c.numeric_facts).length};
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,2));await area.screenshot({path:path.join(out,'table-missing.png')});console.log(report);
 }finally{await browser.close();}
})().catch(e=>{console.log(e.stack);process.exitCode=1;});
