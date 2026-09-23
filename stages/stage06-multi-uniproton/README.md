# Stage 06：双 UniProton 多实例

当前状态：`COMPLETE`（2026-09-21，功能与构建范围）。

M6 已将两个 UniProton 实例固定在 CPU4/CPU5（均为 Cortex-A53），Linux 保留
CPU0～3 和 CPU6/CPU7（两颗 Cortex-A73）。两实例使用独立 ELF、加载地址、MMU
区、128 KiB OpenAMP 共享池和 SGI；最终 Yocto 镜像已完成零警告全量构建、写入
板卡并通过正序/逆序启动、双路并发 RPMsg 和单边生命周期隔离测试。

关键资源：

| 实例 | CPU / MPIDR | SGI | OpenAMP 共享池 | ELF 入口 | MMU 区 |
|---|---|---:|---|---|---|
| UP-A | CPU4 / `0x100` | 8 | `0x7a080000..0x7a09ffff` | `0x7b200000` | `0x7ba00000` |
| UP-B | CPU5 / `0x101` | 9 | `0x7a0a0000..0x7a0bffff` | `0x7c200000` | `0x7ca00000` |

最终结果：

- Linux：`online=0-3,6-7`、`offline=4-5`、`present=0-7`；
- 两实例同时 `Running`，分别注册 RPMsg tty/rpc/umt；
- 正序、逆序及最终镜像烟测累计两路回显 6,000 次，451B payload，全部通过；
- 单边停启隔离正序 50 轮/实例、逆序 20 轮/实例，合计 70 轮/实例，全部通过；
- SGI8/SGI9 独立计数，`Err: 0`，`systemctl --failed` 为空；
- 最终全量构建 `2920/2920` 成功，补丁精确应用，无 warning；
- 配置继续使用 `AutoBoot=no`，便于 M7 做三实例启动顺序和故障隔离。

目录约定：

- `source/`：Linux/MCS 补丁、`mcs_km` 源码和 UniProton M6 覆盖文件；
- `yocto/`：最终配方、defconfig、MICA 配置、服务文件和 rootfs manifest；
- `firmware/`：板上最终运行的 boot、模块、micad 和两个 UniProton ELF；
- `build/`：复建入口、内核配置、FIT 审计和构建摘要；
- `tests/`：双实例回归脚本与实测日志；
- `docs/`：M6 收口报告；CPU5 单实例前置报告仅保留为历史依据。

完整实现、根因和验收记录见 `docs/m6-dual-instance-closeout.md`。M5 登记的 72 小时
稳态仍为后续补测项，本阶段未把它写成已通过，也未启动后台长稳任务。
