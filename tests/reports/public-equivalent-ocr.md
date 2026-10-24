# 扫描OCR验证：公开等价物、非官方 pdf/ 文件

公开等价物、非官方 pdf/ 文件；未运行或宣称官方三用例通过。

结论：**未通过。完整15页合成扫描PDF确实进入PaddleOCR分支，但默认300秒和明确配置的900秒两次均返回OCR_FAILED，有效发布Chunk数均为0。** 不把中间可能识别的文本当合规输出，不声称官方img文件通过。

## 来源与合成方法（公开等价物、非官方 pdf/ 文件）

源为公开arXiv 1706.03762v1：[下载地址](https://arxiv.org/pdf/1706.03762v1)，完整15个物理页；原文件SHA-256 0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476。它与去重用例v1原PDF相同。

使用pdf-pro技能的光栅化/合成流程：pypdfium2 5.14.0逐页以150/72比例渲染RGB，ReportLab 5.1.0 drawImage按原页尺寸合成新PDF；没有抽页、复制小样页顶替、保留原文本层或添加可选中正文。原管线内部仍按既有scale=2（144DPI）渲染OCR输入，模型/阈值/线程参数不改。

合成扫描件5210401字节，15页；首图1275×1651像素；光栅化/合成耗时1.236487秒。首图已实际查看，确认是原论文页面而非空白或人工短句。

合成扫描PDF SHA-256：51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264。pypdf逐页抽取文本长度全部为0：

```json
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

两次合成PDF字节SHA相同，输入未删改；两次均使用POST /api/v1/papers真实上传和既有MinerU→PaddleOCR管线。复用本机28个既有Paddle模型缓存文件，PaddleOCR3.7.0/PaddlePaddle3.3.1，CPU、4线程、现有mobile_det选择，未注入Mock OCR结果。该合成件是公开等价物、非官方 pdf/ 文件，不是用户尚未提供的官方img。

## 两次实跑原始数字

| 配置 | HTTP | OCR分支 | 有效Chunk | 有效文本字符 | 上传耗时秒 | RSS采样峰值字节 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 默认API，300秒引擎时限 | 422 | True | 0 | 0 | 304.962881 | 1303474176 |
| 补测，仅将既有LocalEngines时限设900秒 | 422 | True | 0 | 0 | 904.776897 | 1302269952 |

0指没有通过校验发布的有效文本/Chunk；引擎未返回完整结果，无法知道内部已识别多少，不把0解释成OCR内部从未识别任何文字。RSS每50ms采样整个测试进程及其全部子进程的合计，可能重复计共享页，也可能漏短瞬态；不冒称OS精确高水位。默认与补测private采样峰值分别1960218624 / 1996214272字节。

## 错误响应与状态原文

两次返回相同三字段错误体：

```json
{
  "error_code": "OCR_FAILED",
  "message": "本地 OCR 未完成，请检查依赖、模型与运行时限。",
  "details": null
}
```

默认状态快照：

```json
[
  [
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "queued",
      "progress": 0,
      "current_stage": "等待解析",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "parsing",
      "progress": 5,
      "current_stage": "检查 PDF 与文本层",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "parsing",
      "progress": 30,
      "current_stage": "MinerU 本地文本解析完成",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "ocr",
      "progress": 40,
      "current_stage": "扫描页 OCR",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "failed",
      "progress": 40,
      "current_stage": "解析未完成",
      "error_code": "OCR_FAILED",
      "error_message": "本地 OCR 未完成，请检查依赖、模型与运行时限。"
    }
  ]
]
```

补测状态快照：

```json
[
  [
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "queued",
      "progress": 0,
      "current_stage": "等待解析",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "parsing",
      "progress": 5,
      "current_stage": "检查 PDF 与文本层",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "parsing",
      "progress": 30,
      "current_stage": "MinerU 本地文本解析完成",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "ocr",
      "progress": 40,
      "current_stage": "扫描页 OCR",
      "error_code": null,
      "error_message": null
    },
    {
      "schema_version": "1.1.0",
      "paper_id": "paper-51bc393630fc62cd866604ae5297bf901a268469c00975df972947c2feb39264",
      "status": "failed",
      "progress": 40,
      "current_stage": "解析未完成",
      "error_code": "OCR_FAILED",
      "error_message": "本地 OCR 未完成，请检查依赖、模型与运行时限。"
    }
  ]
]
```

两次均queued→parsing→ocr(40)→failed(40)，未进入indexing。耗时分别约为300/900秒时限加前置解析开销，与超时特征一致；但现有适配器将退出错误、解析错误和TimeoutExpired统一脱敏，本轮未保存底层异常类别，不能声称已精确定位为缺依赖、OOM或某模型缺陷。补测进程结束后，已确认其已知worker PID不再存在。

900秒补测使用create_app已有pipeline_factory入口，仍是原Pipeline与LocalEngines，仅显式设置timeout=900。**生产API默认300秒没有修改，默认失败没有被补测覆盖；900秒也未完成，因此不再继续加大时限重试。**

## 证据与复现（公开等价物、非官方 pdf/ 文件）

完整请求/响应、采样、输入哈希、合成尺寸与状态在[默认JSON](public-equivalent-ocr.json)和[900秒补测JSON](public-equivalent-ocr-extended.json)。生成的PDF、预览PNG、模型缓存及临时解析输入仅在被忽略的D盘data/，未提交。没有真实大模型、DeepSeek调用或API Key，未改任何契约、后端实现或前端文件。

```powershell
backend/.venv/Scripts/python.exe tests/run_public_ocr.py --source data/public-equivalents/dedup-release/inputs/attention-v1.pdf --output-root data/public-equivalents/ocr-reproduce --report data/public-equivalents/ocr-reproduce.json
backend/.venv/Scripts/python.exe tests/run_public_ocr.py --source data/public-equivalents/dedup-release/inputs/attention-v1.pdf --output-root data/public-equivalents/ocr-extended-reproduce --report data/public-equivalents/ocr-extended-reproduce.json --engine-timeout 900
```

输出目录必须尚不存在。以上是公开等价物、非官方 pdf/ 文件验证，不是单页自制OCR烟测，也不声称官方三用例通过。最后完整回归在这两次扫描验证结束后执行；其结果不能替代本项失败。
