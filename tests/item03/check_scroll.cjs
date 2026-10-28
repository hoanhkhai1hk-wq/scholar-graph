// Mathematical alignment invariants, separate from the real browser drag proof.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const ts = require('../../frontend/node_modules/typescript');
const moduleExports = {};
new Function('exports', ts.transpileModule(fs.readFileSync(path.join(__dirname, '../../frontend/lib/bilingual-scroll.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText)(moduleExports);
const map = moduleExports.mapBilingualScroll;
let checks = 0;
const check = (actual, expected) => { checks++; assert.ok(Math.abs(actual-expected)<1e-7, `${actual} != ${expected}`); };
const a = [{id:'a',top:0},{id:'b',top:100},{id:'c',top:300}];
const b = [{id:'a',top:0},{id:'b',top:200},{id:'c',top:260}];
check(map(50,400,500,a,b).top,100);
check(map(200,400,500,a,b).top,230);
check(map(350,400,500,a,b).top,380);
check(map(400,400,500,a,b).top,500);
let previous=-1;
for(let position=0;position<399;position+=3) {
  const forward=map(position,400,500,a,b).top;
  checks++; assert.ok(forward>=previous); previous=forward;
  check(map(forward,500,400,b,a).top,position);
}
check(map(350,400,200,a,b).top,200);
check(map(0,0,500,a,b).top,0);
check(map(100,400,500,[],b).top,0);
check(map(100,400,500,[{id:'missing',top:0}],b).top,125);
console.log(JSON.stringify({passed:true,checks}));
