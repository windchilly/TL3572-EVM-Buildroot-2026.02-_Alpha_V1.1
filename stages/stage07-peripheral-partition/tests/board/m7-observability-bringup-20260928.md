# M7.0 早期日志首轮实机验证（2026-09-28）

本文件保留首轮历史记录；其中发现的双停止 `SIGABRT` 后来已完成修复与回归，当前状态见 [RPC 生命周期修复记录](m7-rpc-log-lifecycle-fix-20260928.md)。

板卡：`192.168.2.141`，openEuler Embedded 24.03-LTS，Linux 6.12.69；管理仍使用 ETH1。此记录仅验收 M7.0 的早期日志第一切片，不代表外设已移交。M6 原始 `up-a/up-b` 固件和配置未覆盖，测试使用 `/root/m7-observe-20260928/` 下的独立 ELF 与临时 `up-a-m7/up-b-m7` 实例。

## 构建与校验

| 实例 | CPU / 固件入口 / 日志区 | ELF SHA-256（最终重编） |
|---|---|---|
| UP1 / up-a | CPU4 / `0x7b200000` / `0x7b000000..0x7b1fffff` | `e42b1a37ab460d34943ae0bd825f72cd5cbdcfc5efd0a2db00b156088738c5bf` |
| UP2 / up-b | CPU5 / `0x7c200000` / `0x7c000000..0x7c1fffff` | `d51461363145044ca6a1b498d301a54c218770a7a4175ef2528d28f62817b47a` |

最终重编只修正 `vsnprintf_s` 失败或截断时的日志回退记录及“恰好填满缓冲区”的计数边界；此前版本通过了下列双实例通信测试，最终 ELF 随后通过了[逐个单实例复测](m7-final-elf-single-instance-20260928.md)，但尚未完成双实例连续停止故障回归。构建源是 M6 UniProton 源码的独立副本 `UniProton-m7`，在该副本上叠加本阶段 patch 和 `print.c`，M6 源码没有被本测试覆盖。

## 已通过

1. 两个测试实例同时启动，分别注册 RPMsg tty/rpc/umt；读取各自保留内存日志，均能看到 CPU 入口、IRQ 路由、调度任务、OpenAMP vring、endpoint 与 RPMsg ready，共 9 条/次。UP1/UP2 的日志地址、CPU 编号和实例身份各自独立，UniProton 不再写 UART0。
2. 复用 M6 双路运行测试，`--echo-count 100 --isolation-cycles 2`：两路各 100 次、每次 451 B 的并发 RPMsg 回显通过；每路分别经历 2 次单边停启。最终两路内存环均为 `boot=3 seq=27`，三次启动序列均完整保留。
3. `up_log_reader.py` 在板上经 `/dev/mem` 直接读取两路日志；同一记录在测试实例停止后、管理进程重启后仍可读取。板卡 `/var/log` 指向易失目录，因此持久日志写在 `/userdata`；两路文件分离、带 Linux 采集时间戳，systemd 测试启动时权限为 `0640`，单文件轮转上限 4 MiB、保留 3 份备份。两路 `m7-up-log@` 服务各自启动后均为 `active`，随后测试停止，未设置开机自启。
4. 本地 `python -m unittest discover -s stages/stage07-peripheral-partition/tests -p 'test_*.py'`：5 项通过。

## 未通过与限制

- 在完成通信压力测试后，顺序执行 `mcsctl stop up-a-m7`、`mcsctl stop up-b-m7`，第二个停止动作使 `micad` 收到 `SIGABRT`。systemd 自动重启该服务，仅重新加载原有 M6 的 `up-a/up-b` 配置；当前管理服务 `active`、无 failed units，原有两实例 `Offline`，板卡 SSH/ETH1 正常。`journalctl -u micad` 可见 `Stopping up-b-m7` 后紧接 `status=6/ABRT`，尚无堆栈，根因待查。不得把单边停启通过等同于双实例收尾通过；修复前不继续反复执行该停启序列。
- 日志目前依赖 root 读取 `/dev/mem`，还没有独立 RPMsg 诊断端点、心跳/超时报警、异常寄存器快照或业务健康判定。断电后未持久化到 `/userdata` 的内存环内容仍可能丢失。Linux 采集时间戳不是 UP 事件时间戳。
- 本轮未迁移 CAN、UART、SARADC、GMAC；当前生效 DT 中这些控制器仍由 Linux 绑定。UART4/8 仍待后续作为工业 RS-232 口迁移；ETH2 保持 Linux 所有权，直到 UP2 直驱验收通过。

## 当前板卡状态与回退

`micad` 为 active；`up-a/up-b` Offline；`m7-up-log@up-a.service` 与 `m7-up-log@up-b.service` 已安装但 inactive/disabled。`/lib/firmware/rk3572-uniproton-up-a.elf` 和 `-up-b.elf` 未更改。只需不启用 M7 临时配置，M6 基线即可继续使用；测试文件位于 `/root/m7-observe-20260928/`，持久日志位于 `/userdata/uniproton-logs/`（另有一次性试读目录 `/userdata/m7-observe-test-20260928/`）。
