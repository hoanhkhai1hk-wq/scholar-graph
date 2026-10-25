// Optional independent parsers, installed only under ignored data/module6-tools.
// No frontend packages/source or runtime dependencies are modified.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'data/module6-tools/package.json'));
const load=async name=>import(pathToFileURL(require.resolve(name)).href);
const result={};
try {
  const {instance}=await load('@viz-js/viz');
  const viz=await instance();
  const source=fs.readFileSync(path.join(root,'tests/reports/module6-topology.dot'),'utf8');
  const svg=viz.renderString(source,{format:'svg'});
  if (!svg.includes('<svg')) throw new Error('No SVG');
  fs.writeFileSync(path.join(root,'tests/reports/module6-topology-dot.svg'),svg);
  result.dot={status:'passed',parser:'@viz-js/viz',version:'3.31.0',graphviz_wasm_rendered:true,
    source_sha256:createHash('sha256').update(source.replace(/\r\n/g,'\n')).digest('hex'),
    newline_normalization:'CRLF_to_LF',svg_sha256:createHash('sha256').update(svg).digest('hex')};
} catch (error) { result.dot={status:'failed',reason:'Independent DOT parser/render did not succeed',type:error.constructor.name}; }
try {
  const {JSDOM}=await load('jsdom');
  const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/'});
  globalThis.window=dom.window;
  globalThis.document=dom.window.document;
  const mermaid=(await load('mermaid')).default;
  mermaid.initialize({startOnLoad:false,securityLevel:'strict'});
  const source=fs.readFileSync(path.join(root,'tests/reports/module6-topology.mmd'),'utf8');
  const parsed=await mermaid.parse(source);
  if (!parsed) throw new Error('No parsed diagram');
  result.mermaid={status:'passed',parser:'mermaid.parse',version:'12.2.0',jsdom_version:'30.1.3',diagram_type:parsed.diagramType,
    source_sha256:createHash('sha256').update(source.replace(/\r\n/g,'\n')).digest('hex'),newline_normalization:'CRLF_to_LF'};
  dom.window.close();
} catch (error) { result.mermaid={status:'failed',reason:'Independent Mermaid parser did not succeed',type:error.constructor.name}; }
fs.writeFileSync(path.join(root,'tests/reports/module6-topology-external-validation.json'),JSON.stringify(result,null,2)+'\n');
process.stdout.write(JSON.stringify(result)+'\n');
process.exitCode=Object.values(result).every(v=>v.status==='passed')?0:1;
