// Run the actual bounded-body helper with a truncated stream; it must not forward a prefix.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),ts=require(path.join(root,'frontend/node_modules/typescript'));
const text=fs.readFileSync(path.join(root,'frontend/lib/server-transport.ts'),'utf8');
const compiled=ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,loaded={exports:{}};
new Function('module','exports',compiled)(loaded,loaded.exports);
(async()=>{
 await assert.rejects(loaded.exports.boundedBody(new Request('http://localhost/test',{method:'POST',headers:{'content-length':'200'},body:'prefix'})),/REQUEST_BODY_TRUNCATED/);
 assert.equal((await loaded.exports.boundedBody(new Request('http://localhost/test',{method:'POST',headers:{'content-length':'6'},body:'prefix'}))).byteLength,6);
 await assert.rejects(loaded.exports.boundedBody(new Request('http://localhost/test',{method:'POST',body:'prefix'}),5),/REQUEST_TOO_LARGE/);
 console.log(JSON.stringify({truncated_body_rejected:true,complete_body_accepted:true,size_limit_enforced:true}));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
