/* Compile the actual reader component into a browser fixture without a web server.
 * API proxying and legacy null-box responses are explicit test infrastructure.
 * Real PDF bytes, OCR output, reader logic and styles come from the project.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const frontend = path.join(root, 'frontend');
const packages = path.join(frontend, 'node_modules');
const { chromium } = require(path.join(packages, '@playwright/test'));
const compiler = require(path.join(packages, 'next/dist/compiled/webpack/webpack'));
compiler.init();
const webpack = compiler.webpack;
const base = 'http://127.0.0.1:8045';
const work = path.join(root, 'data/teacher-feedback-20261114/browser-fixture');
const reportDir = path.join(root, 'test-records/teacher-feedback-20261114');
const shots = path.join(root, 'output/playwright/teacher-feedback-20261114');
fs.mkdirSync(work, { recursive: true });
fs.mkdirSync(shots, { recursive: true });

async function main() {
  const fixtures = JSON.parse(fs.readFileSync(path.join(work, '../fixtures.json'), 'utf8'));
  const loader = path.join(work, 'typescript-loader.cjs');
  fs.writeFileSync(loader, `const ts = require(${JSON.stringify(path.join(packages, 'typescript'))});
    module.exports = function(source) { return ts.transpileModule(source, {compilerOptions: {
      target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true}, fileName: this.resourcePath}).outputText; };`);
  const entry = path.join(work, 'entry.tsx');
  fs.writeFileSync(entry, `import {createRoot} from 'react-dom/client';
    import LayoutViewer from '@/components/LayoutViewer';
    import AnchorTag from '@/components/AnchorTag';
    const f = window.__fixture;
    createRoot(document.getElementById('root')).render(<div onClickCapture={event => {
      const a = event.target.closest('a.sg-anchor-inline');
      if (a) {event.preventDefault(); window.dispatchEvent(new CustomEvent('sg:locate', {detail:f.anchor}));}
    }}><div style={{padding:12}}><AnchorTag anchor={f.anchor} location={f.location}/></div>
    <div data-document-scroll style={{height:'85vh',overflowY:'auto'}}><LayoutViewer
      paperId={f.paper.paper_meta.id} hasTextLayer={f.paper.paper_meta.has_text_layer}
      chunks={f.paper.chunks} references={f.paper.reference_entries} links={f.paper.citation_links}
      bibliographyLocations={f.bibliography}/></div></div>);`);
  await new Promise((resolve, reject) => {
    const c = webpack({mode: 'development', devtool: false, context: frontend, entry,
      output: {path: path.join(work, 'bundle'), filename: 'entry.js', chunkFilename: '[id].js', publicPath: '/feedback-assets/'},
      resolve: {extensions: ['.tsx', '.ts', '.js', '.mjs'], modules: [packages], alias: {'@':frontend},
        fallback: {fs:false,path:false,url:false}},
      module: {rules: [{test:/\.tsx?$/, use:loader}]},
      plugins: [new webpack.DefinePlugin({'process.env': JSON.stringify({NODE_ENV:'development'})})],
    });
    c.run((error, stats) => c.close(() => error || stats.hasErrors()
      ? reject(error || new Error(stats.toString({all:false,errors:true}))) : resolve()));
  });
  const browser = await chromium.launch({channel: 'msedge', headless:true});
  const checks = [], errors = [];
  try {
    for (const [kind, legacy] of [['native',false], ['scan',false], ['native',true], ['scan',true]]) {
      const saved = fixtures[kind];
      const paperFolder = path.join(root,'data/teacher-feedback-20261114/records/papers',saved.paper_id);
      const read = file => JSON.parse(fs.readFileSync(path.join(paperFolder,file+'.json'),'utf8'));
      const paper = {paper_meta:read('paper-meta'), chunks:read('chunks'),
        reference_entries:read('reference-entries'),citation_links:read('citation-links')};
      if (legacy) paper.chunks.forEach(chunk => {chunk.bbox = null;});
      const chunk = paper.chunks.find(c=>c.chunk_id===saved.chunk_id);
      const anchor = {paper_id:saved.paper_id, page_number:saved.page, chunk_id:saved.chunk_id, section:chunk.section_path};
      const fixture = {paper, anchor, location: legacy ? {...saved.location,bbox:null,precision:'page'} : saved.location, bibliography:{}};
      for (const ref of paper.reference_entries) {
        const c = paper.chunks.find(c=>c.section_path.some(s=>/References/i.test(s)) && c.text.includes('['+ref.number+']'));
        if (c) fixture.bibliography[ref.number] = {page_number:c.page_number,chunk_id:c.chunk_id,text:c.text};
      }
      const page = await browser.newPage({viewport:{width:1440,height:1000}});
      page.on('pageerror',error=>errors.push({case:kind,legacy,error:error.message}));
      page.on('console',message=>{if (message.type()==='error') console.log('browser-console',message.text().slice(0,300));});
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/feedback-test') {
          const css = ['globals.css','workbench.css','celadon.css'].map(f=>fs.readFileSync(path.join(frontend,'app',f),'utf8')).join('\n');
          await route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>${css}</style><body><div id="root"></div><script>window.__fixture=${JSON.stringify(fixture).replace(/</g,'\\u003c')}</script><script src="/feedback-assets/entry.js"></script></body></html>`});
        } else if (url.pathname.startsWith('/feedback-assets/')) {
          const file = path.join(work,'bundle',path.basename(url.pathname));
          await route.fulfill({contentType:'application/javascript',body:fs.readFileSync(file)});
        } else if (url.pathname === '/pdf.worker.min.mjs') {
          await route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.join(packages,'pdfjs-dist/build/pdf.worker.min.mjs'))});
        } else if (url.pathname.startsWith('/api/workspace/') || url.pathname.startsWith('/api/backend/')) {
          if (legacy && url.pathname.includes('/evidence/')) {
            const c = paper.chunks.find(c=>c.chunk_id===decodeURIComponent(url.pathname.split('/').at(-1)));
            await route.fulfill({json:c}); return;
          }
          const apiPath = url.pathname.replace('/api/workspace/','/api/v2/').replace('/api/backend/','/api/v1/');
          const response = await route.fetch({url:base+apiPath+url.search});
          await route.fulfill({response});
        } else await route.continue();
      });
      await page.goto(`${base}/feedback-test?page=${saved.page}&chunk=${saved.chunk_id}`);
      const note = page.locator('.sg-layout__note');
      try { await note.waitFor(); }
      catch (error) {
        fs.writeFileSync(path.join(reportDir,'browser-failure.json'),JSON.stringify({errors,body:await page.locator('body').innerText()},null,2));
        await page.screenshot({path:path.join(shots,'failure.png'),fullPage:true});
        throw error;
      }
      await page.waitForFunction(() => document.querySelector('.sg-layout__note')?.textContent?.includes('定位'));
      const text = await note.innerText();
      const label = kind+(legacy?'-legacy':'');
      if (legacy && kind==='scan') {
        assert.match(text,/页级定位/); assert.equal(await page.locator('.sg-pdfpage__hit').count(),0);
        checks.push({case:label,mode:'page-fallback',passed:true});
      } else {
        assert.match(text,legacy?/文本层命中/:/解析坐标/);
        for (const width of [1440,390]) {
          await page.setViewportSize({width,height:1000});
          const handle = await page.waitForFunction(()=>{
            const hit = document.querySelector('.sg-pdfpage__hit');
            if (!hit?.parentElement) return null;
            const h=hit.getBoundingClientRect(), c=hit.parentElement.querySelector('canvas').getBoundingClientRect();
            if (!c.width || !c.height) return null;
            return [(h.left-c.left)/c.width,(h.top-c.top)/c.height,(h.right-c.left)/c.width,(h.bottom-c.top)/c.height];
          });
          const region = await handle.jsonValue();
          if (!legacy) region.forEach((v,i)=>assert.ok(Math.abs(v-saved.location.bbox[i])<.003,`${label} ${width} coordinate ${i}: ${v}`));
          checks.push({case:label,width,region,mode:legacy?'text-fallback':'parser-coordinates',passed:true});
          if (!legacy) await page.screenshot({path:path.join(shots,`${label}-${width}.png`),fullPage:true});
        }
        await page.setViewportSize({width:1440,height:1000});
        await page.getByRole('link',{name:/查看原文/}).click();
        await page.waitForFunction(()=>document.querySelector('.sg-layout__note')?.textContent?.includes('答案证据'));
        assert.equal(await page.locator('.sg-pdfpage__hit').count(),1);
        checks.push({case:label,mode:'citation-click',passed:true});
        if (kind==='native' && !legacy) {
          await page.locator('.sg-layout__backrefs button').first().click();
          await page.waitForFunction(()=>document.querySelector('.sg-layout__note')?.textContent?.includes('参考文献 [1]'));
          assert.equal(await page.locator('#pdf-page-2 .sg-pdfpage__hit').count(),1);
          checks.push({case:label,mode:'bibliography-jump',passed:true});
          await page.getByRole('button',{name:'返回刚才引用处',exact:true}).click();
          await page.waitForFunction(()=>document.querySelector('.sg-layout__note')?.textContent?.includes('已返回第 1 页'));
          assert.equal(await page.locator('#pdf-page-1 .sg-pdfpage__hit').count(),1);
          checks.push({case:label,mode:'citation-return',passed:true});
        }
      }
      await page.unrouteAll({behavior:'wait'});
      await page.close();
    }
  } finally {
    for (const context of browser.contexts()) for (const page of context.pages()) await page.unrouteAll({behavior:'ignoreErrors'});
    await browser.close();
  }
  assert.deepEqual(errors,[]);
  const report = {scope:'Actual LayoutViewer and AnchorTag compiled in isolated browser fixture; real parser/OCR/PDF bytes; v2 proxy and legacy-null responses supplied by test harness. Full Next.js server not started.',checks,errors,passed:true};
  fs.writeFileSync(path.join(reportDir,'browser-component.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
