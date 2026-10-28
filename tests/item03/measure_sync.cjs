const fs=require('node:fs'),path=require('node:path'),ts=require('../../frontend/node_modules/typescript');
const m={};new Function('exports',ts.transpileModule(fs.readFileSync(path.join(__dirname,'../../frontend/lib/bilingual-scroll.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(m);
const root=path.join(__dirname,'../../data/item03-20261028');
const samples=[['before','sync-drag-before.json',0],['after_left','sync-left-after-drag-final.json',0],['after_right','sync-right-after-drag-final.json',1]];
const results=[];
for(const [name,file,index] of samples){const value=JSON.parse(fs.readFileSync(path.join(root,file),'utf8'));const source=value.columns[index],target=value.columns[1-index];const mapped=m.mapBilingualScroll(source.top,source.max,target.max,source.rows,target.rows);results.push({name,input:value.input||'baseline native wheel; unsuccessful scrollbar attempt did not move it',source_top:source.top,target_top:target.top,expected_target_top:mapped.top,alignment_error_pixels:Math.abs(target.top-mapped.top),source_max:source.max,target_max:target.max});}
fs.writeFileSync(path.join(root,'sync-measurement.json'),JSON.stringify({method:'actual DOM paragraph geometry and native input; clipped boundaries allowed',results},null,2));
console.log(JSON.stringify(results));
