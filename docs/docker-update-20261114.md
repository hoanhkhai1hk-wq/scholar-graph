# 教师意见整改后的Docker更新（2026-11-14）

本次修改涉及后端的证据定位、检索融合及前端的PDF阅读器、排序依据。Dockerfile在构建时COPY这些源码，常规部署没有挂载宿主源码，因此更新GitHub仓库后，还需要重建前后端镜像并重新创建容器，才能在Docker网页中使用新功能。

本文件是更新步骤；不表示某台部署机器已经完成更新。此次检查时，本机Docker Desktop Linux引擎未运行，无法读取当前容器状态。

## 在原部署目录更新

先启动Docker Desktop，确认Linux引擎可用。在原来使用的Compose项目目录中执行，沿用原项目名、配置和数据卷。

如果这份部署是从GitHub克隆的独立目录，先同步源码：

```powershell
git pull --ff-only
```

如果就是本次已推送修改的同一份工作区，源码已经在本地，无需重复拉取。保留已有的`.env`与`docker-compose.override.yml`，它们承载本机配置。

随后执行：

```powershell
docker compose config -q
docker compose up -d --build --wait backend frontend
docker compose ps
```

重建使用现有命名数据卷，原论文、OCR结果、问答记录及本地权重继续保存在原卷中。不使用`docker compose down -v`或清理卷命令。仅执行`restart`不会把宿主的新源码构建进旧镜像。

这次没有冻结记录Schema或数据库迁移，不需要为了本次更新清空论文库、重新OCR全部文件或重新下载已有权重。

## 拍摄前核对两个画面

1. 在已保存OCR坐标的扫描件中展开回答依据、点击引用，确认扫描原件高亮目标区域；缩放后仍对齐。无坐标的旧数据仍明确回退到页级定位。
2. 打开“发现与追踪”→“高级检索、手动追踪与兼容接口诊断”，选择原生文字版Attention，执行`Adam optimizer`查询，展开首条结果的“排序依据”。确认显示两路权重和得分贡献，诊断中的向量状态为READY（就绪）。

混合检索解释需要已有BGE-M3权重和可用的容器内向量运行时。缺少模型时系统会如实回退，不把回退画面当作新权重功能演示。若改拍工作台问答中的融合诊断，另需将工作台检索配置为hybrid；本次既定补录拍摄的是高级检索中文面板。

若健康检查失败，先看状态与服务日志：

```powershell
docker compose ps
docker compose logs --tail 100 backend frontend
```

检查日志时保留凭据隐私，不输出完整环境变量或展开后的Compose配置。更新GitHub和更新运行中的Docker服务是两步独立操作，录屏前以实际运行页面为准。
