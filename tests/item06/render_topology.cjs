// Independently render actual generated DOT and Mermaid, without TeX installation.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');const {pathToFileURL}=require('node:url');
const {chromium}=require('../../frontend/node_modules/playwright');
const base=path.resolve(__dirname,'../../data/item06-20261029'),source=path.join(base,process.argv[2]||'live-repaired'),out=path.join(source,process.argv[3]||'rendered');fs.mkdirSync(out);
const req=createRequire(path.resolve(__dirname,'../../data/module6-tools/package.json'));
(async()=>{const responsePath=path.join(source,'topology-response.json'),topology=fs.existsSync(responsePath)?JSON.parse(fs.readFileSync(responsePath)):JSON.parse(fs.readFileSync(path.join(source,'topology-task.json'))).result.topology,expected=Object.values(topology.metadata.script_ids).sort();
 const viz=await (await import(pathToFileURL(req.resolve('@viz-js/viz')).href)).instance();
 const dot=viz.renderString(fs.readFileSync(path.join(source,'topology.dot'),'utf8'),{format:'svg'});fs.writeFileSync(path.join(out,'dot.svg'),dot);
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={};
 try{
  await page.setContent(dot);const nodeIds=await page.locator('g.node title').allTextContents();assert.deepEqual([...nodeIds].sort(),expected);assert.equal(await page.locator('g.edge').count(),topology.edges.length);
  await page.locator('svg').screenshot({path:path.join(out,'dot.png')});report.dot={rendered:true,node_count:nodeIds.length,edge_count:topology.edges.length,renderer:'Graphviz via @viz-js/viz WASM'};
  await page.setContent('<!doctype html><html><body><div id="diagram"></div></body></html>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../data/module6-tools/node_modules/mermaid/dist/mermaid.min.js')});
  const svg=await page.evaluate(async source=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',themeVariables:{primaryColor:'#e4eeea',primaryTextColor:'#183d34',lineColor:'#718b7e',fontFamily:'Microsoft YaHei, sans-serif'}});return (await mermaid.render('item06topology',source)).svg;},fs.readFileSync(path.join(source,'topology.mmd'),'utf8'));
  fs.writeFileSync(path.join(out,'mermaid.svg'),svg);await page.locator('#diagram').evaluate((el,svg)=>{el.innerHTML=svg;},svg);
  const rendered=await page.locator('#diagram .node').evaluateAll(nodes=>nodes.map(n=>({id:n.getAttribute('data-id'),dom_id:n.id})));
  const actual=rendered.map(n=>n.id||n.dom_id.match(/(?:^|-)flowchart-(n\d+)-\d+$/)?.[1]);assert.deepEqual(actual.sort(),expected);
  await page.locator('#diagram > svg').screenshot({path:path.join(out,'mermaid.png')});report.mermaid={rendered:true,node_count:actual.length,renderer:'Mermaid 12 in native Chrome',rendered_nodes:rendered};
  report.tikz={generated:true,compiled:false,reason:'User requires code only; no TeX toolchain installed'};
  report.matplotlib={rendered:fs.readFileSync(path.join(source,'topology.png')).subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.log(e.stack);process.exitCode=1;});
