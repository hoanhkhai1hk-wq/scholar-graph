// Execute the actual, unchanged Next proxy route in memory; no frontend build or writes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const source = fs.readFileSync(path.join(root, 'frontend/app/api/backend/[...path]/route.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const loaded = {exports: {}};
const apiRoot = process.argv[2] + '/api/v1';
new Function('require', 'module', 'exports', compiled)((name) => {
  assert.equal(name, '@/lib/api');
  return {API_ROOT: apiRoot};
}, loaded, loaded.exports);

async function main() {
  const get = await loaded.exports.GET(new Request('http://localhost:3000/api/backend/papers?page_size=1'),
    {params: Promise.resolve({path: ['papers']})});
  assert.equal(get.status, 200);
  assert.equal(get.headers.get('x-sg-upstream-status'), '200');
  const listing = await get.json();
  assert.equal(listing.page_size, 1);
  const pid = listing.items[0].id;
  const post = await loaded.exports.POST(new Request(`http://localhost:3000/api/backend/papers/${pid}/qa`, {
    method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({question: 'How many samples?'})
  }), {params: Promise.resolve({path: ['papers', pid, 'qa']})});
  assert.equal(post.status, 200);
  const answer = await post.json();
  assert.equal(answer.refused, false);
  assert.ok(answer.anchors.length);
  const form = new FormData();
  form.append('file', new Blob(['not a pdf']), 'wrong.txt');
  const upload = await loaded.exports.POST(new Request('http://localhost:3000/api/backend/papers', {method:'POST', body:form}),
    {params: Promise.resolve({path:['papers']})});
  assert.equal(upload.status, 415);
  assert.equal((await upload.json()).error_code, 'UNSUPPORTED_FILE_TYPE');
  console.log(JSON.stringify({route_source_sha256: crypto.createHash('sha256').update(source).digest('hex'),
    proxy_get_status: get.status, proxy_qa_post_status: post.status, proxy_multipart_status: upload.status,
    upstream_origin_header: '代理源代码不转发 Origin，服务端请求无需 CORS',
    scope: '实际代理函数内存执行；未构建前端，未验证浏览器页面'}));
}
main().catch(() => {console.error('Proxy compatibility verification failed.'); process.exit(1);});
