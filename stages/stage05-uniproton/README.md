# Stage 05：单 UniProton

状态：`COMPLETE`（当前功能与构建范围）。72 小时稳态和故障注入登记为延期补测。

## 目录

| 目录 | 内容 |
|---|---|
| `docs/` | 最终 M5.3 收口报告和源码覆盖包说明 |
| `source/` | 内核/MCS/UniProton 补丁及最小源码覆盖包 |
| `firmware/` | 最终 boot、UniProton ELF、micad 和 mcs_km.ko |
| `yocto/` | 镜像配方、bbappend、systemd 配置和最终 manifest |
| `tests/` | 当前回归脚本、延期长稳脚本及中止快照 |
| `build/` | 最终重建入口和 UniProton 构建日志 |

正式交付物统一由根目录 `SHA256SUMS` 校验。已被最终报告、源码覆盖包和正式补丁
取代的 M5.1/M5.2 过程脚本、诊断固件及串口日志已清理，不再保留第二套历史入口。

入口文档：`docs/m5.3-single-instance-closeout.md`。
