# M7.0 最终 ELF 单实例冒烟测试（2026-09-28）

本文件记录修复前的单实例测试历史；双实例连续停止故障后来已完成修复与回归，当前状态见 [RPC 生命周期修复记录](m7-rpc-log-lifecycle-fix-20260928.md)。下文保留当时的故障证据和判定。

板卡 `192.168.2.141`。测试前原 M6 `up-a/up-b` Offline，`micad` active、无 failed units，ETH1 对应 Linux `eth0` 为 `192.168.2.141/24`，原始 M6 固件 SHA-256 与 Stage06 记录一致。仅替换 `/root/m7-observe-20260928/` 中的临时 M7 ELF，未覆盖 `/lib/firmware/`。

| 实例 | 最终 ELF SHA-256 | 结果 |
|---|---|---|
| UP1 / CPU4 | `e42b1a37ab460d34943ae0bd825f72cd5cbdcfc5efd0a2db00b156088738c5bf` | 单实例 PASS：启动、RPMsg、日志、100 次回显、停止及移除 |
| UP2 / CPU5 | `d51461363145044ca6a1b498d301a54c218770a7a4175ef2528d28f62817b47a` | 重启恢复后单实例 PASS：启动、RPMsg、日志、100 次回显、停止及移除；首次尝试被残留 CPU 状态阻断 |

## UP1 观测

`mcsctl create/start up-a-m7` 成功，状态 `Running`，RPMsg tty/rpc/umt 注册。保留内存日志从 `boot=3 seq=27` 增至 `boot=4 seq=36`，新增完整的 CPU4 入口、IRQ、调度器、OpenAMP、RPMsg ready 共 9 条。复用 M6 `dual-runtime-regression.py` 的单 pair 模式，`--echo-count 100 --payload-size 451` 通过，收到 47800 B，耗时约 0.066 s。`m7-up-log@up-a` 服务 active 时把此次 `boot=4` 记录写入 `/userdata/uniproton-logs/up-a.log`。随后先停止日志收集服务，再单独 `mcsctl stop` 和 `rm up-a-m7`，均成功；`micad` active，ETH1 地址不变，仅原 M6 两实例 Offline。

## UP2 首次阻断与重启后复测

在 UP1 临时实例已移除后创建 `up-b-m7` 成功，但 `mcsctl start` 打印 `start up-b-m7 failed!`，命令进程却返回退出码 0。`journalctl -u micad` 为 `boot client os on CPU5 failed, err: -1`；内核为 `mcs: boot clientos failed(-4)`。本地 MCS 内核源码显示此值直接来自 PSCI `CPU_ON`，本地 Linux 头文件将 `PSCI_RET_ALREADY_ON` 定义为 `-4`。UP2 保留内存仍为旧记录 `boot=3 seq=27`，未出现新日志，也没有 `/dev/ttyRPMSG*`；因此 `mcsctl status` 的 `up-b-m7 Running` 为误导状态，不能当作成功。

这与上次 `micad` 在停止 UP2 时 `SIGABRT`、CPU5 可能未完成关机的现象一致。未向该假 `Running` 实例发 RPMsg 数据，也未尝试重复启动或双实例连续停止。经用户明确允许，执行一次板卡 `reboot`；约 10 秒后 SSH、`micad`、ETH1 恢复，原 M6 两实例均 Offline，原固件哈希不变，无 failed units，日志收集服务仍 disabled。

重启后重新单独创建并启动 `up-b-m7` 成功，RPMsg tty/rpc/umt 注册到 `/dev/ttyRPMSG0`。保留内存日志从 `boot=3 seq=27` 增至 `boot=4 seq=36`，新增完整 CPU5 入口至 RPMsg ready 的 9 条。说明此次**温重启**并未清空该保留内存环；不能据此推断断电保持。单 pair 回显 `--echo-count 100 --payload-size 451` 通过，收到 47800 B，约 0.065 s。`m7-up-log@up-b` 将 `boot=4` 写入 `/userdata/uniproton-logs/up-b.log`。之后先停日志服务，再单独 `mcsctl stop`、`rm up-b-m7`，均成功。

最终板卡状态：`micad` active、无 failed units，仅原 M6 `up-a/up-b` Offline，ETH1 `eth0` 仍为 `192.168.2.141/24`；两路 M7 日志服务 inactive/disabled。**双实例连续停止曾触发的 `micad SIGABRT` 尚未修复**，本次单实例 PASS 不覆盖该故障。测试自动化不得仅依赖 `mcsctl` 退出码：本次失败的 `start` 仍返回 0，且 `status Running` 也可能是假阳性，须联合 RPMsg 注册、日志新 boot 序号和内核返回码判定。
