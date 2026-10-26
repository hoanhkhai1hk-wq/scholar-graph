# 原文 PDF 文件端点验收

日期：2026-10-26（Asia/Shanghai）。本单为后端单，官方输入标注为 **官方 pdf/ 真文件**；自制单元样例与公开 arXiv 下载分开说明。没有修改前端、契约、API草案、prompts/、experiments/、test-records/；未调用真实模型或使用 Key。

## 最终端点与实现

最终路径：**`GET /api/v1/papers/{paper_id}/file`**，沿用既有 `/api/v1` 前缀。成功返回原始 PDF 字节，`Content-Type: application/pdf`、`Content-Disposition: inline; filename="paper.pdf"`。论文详情 Link 增加 `rel="file"`。不是文本 pane 内容、重排 PDF 或重新生成的文档。

原有上传和 arXiv 抓取会删除临时 PDF；此前解析记录没有附原件。本单在成功解析/门禁后、临时文件删除前增加原件归档：

- 单个与批量上传共用 `UploadService._one` 保留原件；新的 arXiv 下载由既有 `ArxivFetcher.fetch_metadata` 管线保留。
- 当前数据目录 `original-pdfs/index.sqlite3` 保存内部映射（论文id、服务器随机文件名、SHA-256、字节数），原件文件名为随机UUID，不采用用户上传名或请求id。它是内部存储索引，不是新增业务契约，十二份既有 Schema 均不变。
- 请求 id 只用于格式校验及参数化 SQL 查询，不拼接文件路径。数据库中的文件名还要经过UUID格式、目录边界、symlink检查，损坏索引不能指定外部路径。
- 归档以64 KiB块复制并计算SHA-256，与已入库 PaperMeta.file_hash 相等才原子发布和提交映射；SQLite连接显式关闭。每次 GET 以64 KiB块做完整性预检，再由 FileResponse 分块发送；不会加载整份 PDF或整篇Chunk。GET哈希预检会先顺序读完整个文件，内存有界，但会增加一次磁盘读；不宣称首字节零等待。
- FileResponse 支持206 Range，范围非法/越界分别400/416，保留三字段错误封装。CORS新增 Range/If-Range 和相关响应头，供下一段阅读器使用。[框架行为依据](https://starlette.dev/responses/#fileresponse)。

本单仅保证文件端点与归档流程的有界内存；没有改写原有解析器或 arXiv 客户端在 POST/解析期间的内存方式。前端 pdf.js 尚未在本单接入或验收。

开工 `git pull --ff-only` 为 `Already up to date.`，主干 **a60dffd2bb94e8542bf2874e2c0fe4f430ae992f**，工作区干净。原件 GET 的最终复核源提交为 **cb7b0ea98e2ba73252d93b07b4e26203c6e155b7**。

## 官方 Attention v7 上传与字节对照

输入 `D:\AI_Workspace\Tasks\scholar-graph\pdf\1706.03762v7.pdf`。实测从空数据目录上传，使用真实本地 MinerU，POST返回201，耗时7.154795秒；没有复用旧Chunk冒充该次新上传。数据保留在被忽略的 `data/pdf-file-acceptance/2f3ce3880f474e26a8fffc40c66a0de7/`。结构化原始结果见 [实测 JSON](pdf-file-endpoint-live.json)。

论文id：`paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697`。

| 对照对象 | 字节数 | SHA-256 |
| --- | ---: | --- |
| 官方 pdf/ 真文件 v7 | 2,215,244 | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 |
| 入库 PaperMeta.file_hash | — | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 |
| 文件端点完整响应 | 2,215,244 | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 |
| 服务端 ASGI 分块累计 | 2,215,244 | bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697 |

响应头和状态原文摘要：

```text
200
content-type: application/pdf
content-disposition: inline; filename="paper.pdf"
```

服务端实际发送 **34块，最大65,536字节**；测试只在发送钩子累计哈希与长度，没有把整个响应拼成一个 bytes。另有自制有效PDF附2 MiB附件的回归测试：禁用 Path.read_bytes 后仍能返回，逐个 ASGI body 块均不超过64 KiB，累计哈希一致。TestClient 本身可能缓冲客户端收到的数据，服务端分块证据由直接 ASGI 发送钩子取得，二者不混淆。

`Range: bytes=0-31` 实测206；端点测试验证32字节与原件前32字节相同、Content-Range正确、本地两种Origin的浏览器预检成功。

## 未知 id 与穿越防护实测

| 请求id/路径片段 | 状态 | 结果 |
| --- | ---: | --- |
| paper-unknown | 404 | PAPER_NOT_FOUND，说明没有本地原件 |
| %2e%2e%5cprivate | 404 | 反斜杠穿越拒绝 |
| %2e%2e%2fprivate | 404 | 斜杠穿越无匹配资源 |
| %252e%252e%255cprivate | 404 | 双重编码穿越拒绝 |
| paper%27%20OR%201=1-- | 404 | 非法id拒绝，不作为SQL语句执行 |

以上错误体均严格三项 `error_code/message/details`，没有文件内容或本地绝对路径泄漏。单测另覆盖 `..`、Windows盘符输入、数据库映射被改成 `../source.pdf`（422拒绝）、原件损坏（422拒绝）、归档SHA不符（不注册/不残留PDF）、应用重建后映射仍能读取。

未知id响应原文：

```json
{"error_code":"PAPER_NOT_FOUND","message":"无该论文的本地 PDF 原件；历史记录需重新上传同一原件补齐。","details":null}
```

## arXiv：区分实际下载成功与元数据查询失败

**真实重新下载、入库和文件返回已验证。** 使用上一单真实公开 Atom 响应中已验证的1706.03762v7元数据（`module-four-smoke.json` 的 `LIVE-public-arxiv-reference`），本次通过原 `ArxivFetcher.fetch_metadata` 从 `https://arxiv.org/pdf/1706.03762v7` 重新下载PDF，在另一个全新数据目录走既有 MinerU 解析入库。不是拿宿主机旧PDF冒充网络下载。

最新实际下载/解析归档耗时 **7.555025秒**，succeeded=true、error=null。下载的2,215,244字节、入库file_hash与随后文件端点200响应的SHA-256均为上表同一值。返回类型为application/pdf和inline，服务端仍是34块/最大64KiB。单元测试另用自制Atom/PDF验证完整抓取端点的保存及重复抓取不产生第二份原件。

**本次新元数据查询没有通过。** 对 `POST /api/v1/retrieval/fetch` 的实时查询，外层按原操作封装返回HTTP200，但结果 succeeded=false，原因原文：

```json
{"error_code":"UPSTREAM_ERROR","message":"arXiv 公共接口返回 HTTP 429，未取得所需记录或文件。","details":null}
```

因此没有把“已验证的历史元数据+本次真实PDF下载”写成“本次Atom查询成功”。实测JSON保留 `fresh_public_arxiv_passed=false` 和总探针 `passed=false`；文件端点检查 `endpoint_checks_passed=true`，`verified_metadata_arxiv.succeeded=true`。失败项没有被覆盖或计为通过。本单未修改 arXiv 查询策略。

## 历史原件缺失的处理口径

从上一单真实arXiv入库记录复制经门禁校验的四类记录到空测试目录，明确复用的是历史解析记录，不称其为本次新解析：

1. 首次GET原件返回404，原因是旧实现没有保留下载文件。
2. 通过上传端点重新提交**同一SHA-256**的官方v7，POST201；原有论文哈希身份及arXiv元数据不变，建立原件映射。
3. 再GET返回200/application/pdf/inline，2,215,244字节和SHA-256一致。

处理规则：历史或手工/CLI导入记录缺原件时明示404；可重新上传同一原件补齐。不根据请求路径、近似标题或arXiv最新版猜原文件，不把其他版本替换成已入库原件。已有arXiv身份的幂等抓取仍复用旧记录，不自动替历史缺件重新下不同版本。新成功抓取则在清理临时文件前保留当次实际下载件。

## 测试与复现

新增15项文件端点/归档测试，覆盖实际自制PDF上传、重启持久化、Range与统一错误、本地CORS、7种未知/穿越输入、历史缺件、自制arXiv抓取幂等、SHA不符、存储损坏、映射穿越和大PDF发送块上限。单元输入为自制样例，非官方pdf/验收；上面的官方Attention与实际arXiv下载是独立探针证据。

```powershell
backend/.venv/Scripts/python.exe tests/run_pdf_file_acceptance.py
backend/.venv/Scripts/python.exe tests/run_pdf_file_acceptance.py --verified-metadata-download
backend/.venv/Scripts/python.exe -m pytest tests -q --run-ocr --basetemp data/pdf-file-final-regression --junitxml tests/reports/pdf-file-endpoint-pytest.xml
backend/.venv/Scripts/python.exe tests/audit_pdf_file_acceptance.py
```

第一条含实时arXiv元数据查询，429时退出1并保留失败；第二条使用历史验证过的元数据独立验证真实PDF下载，不假造新元数据。两条均写清真实来源。

全量回归最终输出原文：

```text
547 passed, 5 skipped in 180.53s (0:03:00)
```

JUnit合计552项、547通过、5跳过、0失败、0错误。5项为未启用的真实DeepSeek测试，未计为通过。JUnit为 [pdf-file-endpoint-pytest.xml](pdf-file-endpoint-pytest.xml)。首轮发现旧端点总数断言28与新增后的29不符（1失败），已将预期更新为29并明确断言新路径存在，重新跑全量，未删除原有测试。真实模型测试本单不启用，按既有规则跳过；真实自制扫描件OCR启用。

审计见 [pdf-file-endpoint-audit.json](pdf-file-endpoint-audit.json)，重核官方SHA、实际归档字节、流式计数、未知与穿越错误、真实下载哈希、历史补齐、pdf/忽略、保护目录零改动及最终JUnit；不会用审计通过掩盖arXiv元数据429。

## 下一段前端对接信息

交由用户转达WorkBuddy：pdf.js的文件URL为 `/api/v1/papers/{paper_id}/file`；原件缺失404需要提示重新上传原件，不能用文本pane伪装版式原文。Range与本地CORS已准备；本单没有改前端，也没有声称阅读器已嵌入。
