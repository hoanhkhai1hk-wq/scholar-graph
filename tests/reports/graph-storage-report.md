# 第 0 项：Windows 原子发布诊断与缓解

日期 2026-10-24。开工基线 de74511f9f579af910bd683820b409698a301020。

修复前，原四项去重端点测试加原 101 条分页测试连续执行 10 轮，50 项全部通过，未能自然复现 WinError 5。完整命令结果见 graph-storage-before.json。旧 JUnit 中的两次 WinError 5 仍是有效历史证据；本轮不能据此宣称找到了杀毒软件、外部占用进程或 ACL 根因。源码 write_json 已使用 with 关闭文件，并 flush/fsync；没有证据表明原实现遗留自身句柄。

Windows 原生 CreateFileW 受控实验故意不允许 FILE_SHARE_DELETE，直接重命名真实目录失败，实际错误是 **WinError 32**。0.12 秒后关闭该句柄，有限退避后成功，完整 JSON 数据保持完整。见 graph-storage-lock-probe.json。该实验只证明共享锁机制及缓解有效，**不等于复现历史 WinError 5，也不证明历史占用者身份**。

已采取缓解：原子目录 rename、状态文件 replace 和清理操作，在 Windows 且错误码为 5/32/33 时最多尝试 8 次，退避 0.025、0.05、0.1、0.2、0.4、0.8、1.6 秒。每个操作合计等待上限 3.175 秒。等待让临时占用者有时间关闭句柄；永久拒绝访问仍会失败，最后一次原样抛出异常。不存在/目标已存在等非锁错误不重试，其他平台不重试。

没有复制半成品到公开目录、覆盖既有记录、改权限、禁用安全软件或吞掉错误。所有内容仍先校验再写同盘临时目录，成功 rename 才发布整组。清理仍验证绝对路径位于允许父目录；永久模拟拒绝访问时目标与临时目录均未泄漏，测试核对异常确实抛出。

修复后重复同样 10 轮，50 项通过，见 graph-storage-after.json。第 0 项全量回归（图谱代码写入前）原文：

```text
148 passed in 95.78s (0:01:35)
```

graph-storage-regression.xml 为 148 总数、148 通过、0 失败、0 错误、0 跳过，含真实 OCR。新增 8 项覆盖三种可重试错误码、永久错误仍抛出、三种非锁错误不重试、真实 Windows 共享锁释放。原有 140 项未删除或跳过。

依据：[Microsoft CreateFile 共享模式](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)。删除共享权限也影响重命名；原生实测与文档支持退避等待的机制，不支持对未知历史错误进程的归因。
