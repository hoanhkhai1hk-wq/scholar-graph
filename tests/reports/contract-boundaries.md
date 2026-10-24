# v1.1 契约边界验证报告

自制契约样例、非官方 pdf/ 用例；结构边界验证，不证明真实论文解析或数字事实正确。

运行时间：2026-10-24T09:17:48.709820+00:00
脚本提交：`de356d567c6b7b358843a9882d65e77a65cf4c7f`
脚本 SHA-256：`707fd2930f010d932650263e42d526e9eb4c6943774be8ccf76e567ef897dd4e`

总数：722；通过：722；失败：0。
计数来自实际执行的唯一用例，没有通过重复复制或断言固定总数补齐 722。

| 用例分类 | 数量 |
| --- | ---: |
| anchor_shape | 4 |
| chart | 10 |
| dedup | 9 |
| diff | 8 |
| error_envelope | 8 |
| parse_errors | 8 |
| parse_progress | 618 |
| required_extra_version | 35 |
| shared_error_codes | 22 |

九份 Schema 与 example 校验通过；预检不计入边界用例数。

复现（仓库根目录 PowerShell）：

```powershell
backend/.venv/Scripts/python.exe tests/verify_contract_boundaries.py --report-dir tests/reports
```

环境：Python 3.12.15，jsonschema 4.26.0。
完整用例结果、期望/实际判定和十八份输入文件 SHA-256 见同目录 contract-boundaries.json。
包含故意无效输入：这些输入被 Schema 拒绝才算用例通过。
ChartOutput 的 false-check 用例只证明布尔字段形状可接受，不表示该数字可写入图注。
没有运行官方三用例，也没有证明锚点外键真实性；实际管线的语义校验另测。
