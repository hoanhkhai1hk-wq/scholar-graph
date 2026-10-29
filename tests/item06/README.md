# 第6项复现

本项隔离入口3440/8140，数据在`data/item06-20261029/records`。复制第5项20篇已解析论文后，写作只选Attention、LoRA、InstructGPT，另上传一份明确标注的人工中文验收稿。原始官方PDF不进入Git。

顺序：`common.py`保存工作树与原PDF哈希；`prepare.py`复制隔离库；`measure_csv.py`实际测量NumPy矩阵运算；`create_chinese_fixture.py`生成并逐页渲染中文验收稿；`baseline.py`/`browser_baseline.cjs`留存修复前失败；`live_models.py --run NAME`跑真实生成与中译英；`browser_acceptance.cjs NAME`操作真实网页；`render_native.py`执行实际下载的Matplotlib代码；`render_fixed_graph.py NAME`按相同真实模型逻辑生成最终样式代码；`render_topology.cjs NAME rendered`用Graphviz和原生Chrome中的Mermaid独立渲染。

`run_related.py --run NAME`包含第5项回归及本项全量相关套件；另跑快速回归。`build_runtime.py`基于第5项可用镜像做源码覆盖，前端须先生产构建。`release_runtime.py`保持原数据位置更新四套部署。`runtime_audit.py`核对8个服务、源码、DNS、库数量、100份不可变文件，以及仅追加中文稿的原件索引。索引SQLite本身会随上传改变，不能把其文件哈希当作不可变记录。

所有模型值从本地配置读取，禁止写值入Compose/日志。`font-mount.yml`与发布覆盖只读挂载本机自有中文字体，不把字体文件加入Git或镜像；其他环境可用`SG_CJK_FONT_PATH`指定可用的中文字体。绘图仍沿用已有Matplotlib、Graphviz WASM、Mermaid与Chrome，不安装TeX编译链。

CSV是本机真实运算计时，非论文复现实验或模型准确率。线程数设置只是请求，未独立测量实际线程数。中文稿是术语/数字验收输入，不冒充已发表论文。浏览器命中缓存须记录缓存命中，不算新的模型生成。
