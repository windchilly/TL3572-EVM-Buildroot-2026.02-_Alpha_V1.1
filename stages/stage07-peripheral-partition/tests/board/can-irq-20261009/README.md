# CAN1 / FD1 ↔ CAN3 / FD3：自主资源初始化与中断收发

2026-10-09，`192.168.2.141`，M6 openEuler 运行镜像，UP1=CPU4、UP2=CPU5。
**最终固件三轮 PASS：每轮 10,000 次请求及 10,000 次应答，两路各自 TX/RX=10,000/10,000，
TXIRQ/RXIRQ=10,000/10,000，错误、溢出和错误核心中断计数均为 0。**
累计最终版 30,000 次请求及 30,000 次应答；不把早期原型的一轮混入最终版累计数。

这是经典 CAN 的自主门控/分频/复位/pinmux 配置及 IRQ 数据面验证，
不是 CAN FD/BRS、四路 CAN、持久 DT 移交或冷启动验收，M7.0 仍未完成。

## 接线、资源与实现

沿用用户已接好的 FD1↔FD3：H↔H、L↔L、共地，两端终端电阻（J9/J13）。
只接这两个测试口，不接真实执行器；禁止同一接口 H/L 互短。
经典 CAN、标准 ID、8 字节，UP1 发送 `0x321` 请求，UP2 返回 `0x456` 应答，
逐帧检查序号及全部有效载荷。GPLL=1,188 MHz、own divider=/4，baudclk=297 MHz，
NBTP=`0x1200256d`，位速率约 996,644 bit/s（名义 1 Mbit/s）。

| 资源 | UP1 / CAN1 / FD1 | UP2 / CAN3 / FD3 |
|---|---|---|
| CPU / MPIDR | CPU4 / `0x100` | CPU5 / `0x101` |
| 控制器 MMIO（各映射 4 KiB） | `0x2ab10000` | `0x2ab30000` |
| 波特率时钟选择/分频（mask `0x3f80`） | `0x26090404` | `0x26090408` |
| 共享 gate / reset 地址 | `0x2609082c` / `0x26090a2c` | 同左 |
| 本实例 gate/reset mask | `0x0600` | `0x6000` |
| IOC mux 地址 / mask / value | `0x2608608c` / `0xff00` / `0xdd00` | `0x2608203c` / `0x0ff0` / `0x0dd0` |
| 引脚 / mux | GPIO4_B6/B7 / 13 | GPIO1_D5/D6 / 13 |
| SPI / INTID / 实测 target bit | 153 / 185 / `0x10` | 155 / 187 / `0x20` |

代码：[rk3572_can_irq_test.c](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_irq_test.c)，
构建/MMU 钩子：[0003 补丁](../../../source/patches/uniproton/0003-rk3572-can-irq-test-hook.patch)。
最终 MMU 只增加本实例 CAN 页、CRU 页和本实例 IOC 页；不映射对方 CAN/IOC 页。
GIC 窗口从原 16 MiB 缩到 16 KiB。CRU/GIC 仍是共享物理资源，页映射不是硬件防火墙；
软件只写自己的 HIWORD 字段、SPI W1S/W1C 位及 target/priority byte，
不改共享 GIC group/config word、GPLL/CPLL 或系统总线根时钟。
安全组寄存器访问视图仍未独立确认，不能把 IGROUPR 读零当成安全组结论。

执行器在两 UP 确认 PSCI OFF、Linux 接口 DOWN 且驱动解绑后，保存寄存器状态，
故意关闭两路自己的 gate、保持 reset、把 divider 改成 /16。
本轮没有执行 Linux `ip link ... up` 或 bitrate 初始化；随后由各 UP 写自己的
gate、reset、divider 和 mux，读回检查，再初始化控制器。
**pinmux 没有先故意置错**，所以证明了 UP 写入/校验 mux，未证明上电未知 mux 下启动。
共享 PLL/父级总线、已有 M6 平台启动及 transceiver 板级条件仍由系统准备。

UP 读取本核 banked ITARGETSR0 发现目标位，注册 UniProton handler，再用 GICv2
byte/W1S 操作路由本实例 SPI。TX 完成和 RX watermark 由 ISR 处理；
只有 ISR 消耗硬件 RX FIFO，任务等待软件状态并校验数据，不轮询硬件 FIFO/完成标志。
`rxirq` 统计 ISR 消耗的帧数；本轮每帧一个 watermark，实际 `irq=20000`，
TXIRQ/RXIRQ 各 10000。RPMsg 和 Linux 内存读取仅用于启动/日志，不代理 CAN 帧。
实现是单请求在途的双实例冒烟测试，不是生产用多帧队列、bus-off 恢复或实时性驱动。

## 实机测试与回收

| 记录 | 固件 / 条件 | 每路 TX/RX | 每路 IRQ / TXIRQ / RXIRQ | 结果 |
|---|---|---|---|---|
| [run-01.log](run-01.log) | 早期原型；两 IOC 页均映射 | 10000 / 10000 | 20000 / 10000 / 10000 | PASS；不计入最终版累计 |
| [run-02-final.log](run-02-final.log) | 最终单 IOC 页；常规；B→A 停止 | 10000 / 10000 | 20000 / 10000 / 10000 | PASS |
| [run-03-cpu-load.log](run-03-cpu-load.log) | 最终版；Linux 四个 nice=19 CPU worker；B→A 停止 | 10000 / 10000 | 20000 / 10000 / 10000 | PASS；worker 已回收 |
| [run-04-reverse-stop.log](run-04-reverse-stop.log) | 最终版；A→B 停止 | 10000 / 10000 | 20000 / 10000 / 10000 | PASS |

以上均 B→A 启动。四个低优先级 worker 不等于 Linux 全核饱和，未测硬实时延迟/抖动。
最终版每轮控制器 TXERR/RXERR、IRQ error flags、overflow、wrongcpu 均为 0。

结束前 UP 自行屏蔽 CAN、复位控制器模式、禁用 SPI、清 pending，并恢复 target/priority byte。
执行器停止/删除临时实例，确认 CPU4/5 PSCI OFF，**在宿主恢复寄存器之前**检查：

```text
UP IRQ QUIESCE intid=185 enabled=False pending=False active=False target=1
UP IRQ QUIESCE intid=187 enabled=False pending=False active=False target=1
```

然后按原 mask 恢复 own CRU/IOC/IRQ 状态，核对其余 CAN gate/reset/分频/mux 位没有变化，
最后重绑 Linux CAN1/CAN3。任一 CPU OFF 未确认则不恢复、不重绑，不自动重启板卡。
`micad` 全程 PID=311、active、NRestarts=0，两种停止顺序均未复现 SIGABRT。
这不覆盖已知的另一处 MCS 全局 `mcs_fd` create/rm 泄漏问题。

[final-board-state.log](final-board-state.log) 和 [final-resource-snapshot.json](final-resource-snapshot.json)
确认最终原 `up-a/up-b` Offline，CPU4/5 OFF，四路 CAN 绑定 Linux 且 DOWN，
ETH1（Linux eth0）UP、SSH 可用、systemd failed units=0。boot_id 与实施前相同，
本轮无重启、无刷机，原 M6 ELF、实例配置及 DT 未覆盖。
最终快照脚本的 `owner` 表示规划归属；`not_verified` 表示**该只读快照自身**不能验证的项目，
不撤销本报告的在线 IRQ/初始化证据。重绑后 Linux 重新使能 SPI、target=1 是预期结果。

执行器：[run_can_irq_pair.py](../run_can_irq_pair.py)，依赖
[run_can_direct_pair.py](../run_can_direct_pair.py)、[can_resource_preflight.py](../can_resource_preflight.py)
及已安装的独立内存日志读取器；负载入口：[run_can_irq_with_cpu_load.py](../run_can_irq_with_cpu_load.py)。
复测前必须确认固件、接线、原实例均 Offline 和两 CPU OFF，不能直接在有业务流量的系统运行。

## 构建、复建与版本

主仓库父提交 `6120de752182512e99481764c29a9e7a746b2c89`，加本次跟踪的源码/三份补丁/脚本。
完整 M6 源码与依赖输入已在 `repro-inputs/`；固定历史源码 tar 不回写，
当前 M7 IRQ 有效源码由完整 M6 基线加本目录覆盖和补丁组成，不能只拿旧 M7 tar 复建新功能。
操作入口见 [build/README.md](../../../build/README.md)，IRQ 开关在准备、编译时均需 `ON`，默认仍为旧模式。

本轮实际构建环境：`10.100.60.226` 的 `dev_openeuler`，
项目 `/home/openeuler/build/tl3572-2oo3`，Arm GNU 14.3.Rel1 / GCC 14.3.1。
实测源码树 `src/UniProton-m7-can-irq-20261009`，
第二棵独立源码树 `src/UniProton-m7-can-irq-repro-20261009`。
第二棵重新复制未加 M7 补丁的完整 M6 基线、应用 0001/0002/0003、覆盖源文件，
在新 `m7-can-irq-up-a/up-b` CMake 目录编译，而非复用第一棵应用对象。
两次沿用已完成构建的 M6 库；**本轮没有再次从空系统构建 UniProton 库或整个 Yocto 镜像**。
换机时先用已有 [空目录入口](../../../../../repro-inputs/rk3572/README.md) 的 `m6-up`
从源码生成这些库，再执行 IRQ 构建。Stage06 完整源码快照上的三补丁顺序应用也已核验。

构建证据：[build.log](build.log)（原型），[build-final.log](build-final.log)（收紧 IOC 映射后），
[build-repro.log](build-repro.log)（第二棵完整应用复编），
[runtime-rebuild-check.log](runtime-rebuild-check.log)（编译器版本、ELF 与运行镜像校验）。
保留了基线 libc/proxy 编译 warning 和 RWX LOAD 段 warning，没有把“编译成功”写成无 warning。

| 产物 | SHA-256 |
|---|---|
| 最终实测 UP1 ELF | `51fa0a5321cc6f6ded061788c14e64dd2c958ccb5b22032512d4893aeea8f0ea` |
| 最终实测 UP2 ELF | `a61f220f7910d2b04aedbbab5b4059626a6a416a374e44273b43e6e75b742b8c` |
| 第二树 UP1 ELF | `461cbbe53849b29a17cf3c4627bb60ad55b7a66109e3510939b4ed840a576f09` |
| 第二树 UP2 ELF | `58f28551baab60335304fba5c3445f0386f14bef93974ba7b536ac931abe9f2e` |
| UP1 两树 `objcopy -O binary` | `67a520a13cc9c865bfc55e4386a38850df09010ad04a4a12d3ecf2f32f213a49` |
| UP2 两树 `objcopy -O binary` | `bc9282d241902beb347d23f026ccc869da22d36ca83415480f03584757e39d79` |

第二树 ELF 含不同源码路径的调试信息，整文件 hash 不同；去调试的运行镜像逐字节比较均一致。
最终实测两 ELF（609336/609376 B）保存在 [firmware/](../../../firmware/)，不替换原轮询固件。
日志及本轮输入的校验见 [SHA256SUMS](SHA256SUMS)，路径相对本目录；本地 17 项单测全部 PASS。

## 仍待验证 / 下一步

1. 当前接线继续开发 CAN FD/BRS，分别验证 16/32/64 字节、速率组合及错误恢复，不能套用经典 CAN PASS。
2. FD2/FD4 逐口映射、接线和 IRQ 测试；四路并发、单边重启和长时稳定性。
3. 独立 M7 DT 禁用对应 Linux 节点、启动所有权/共享根资源管理、未知 pinmux/冷启动与回退验证。
4. 外部对端与逻辑分析仪验证丢包/时延/抖动；UART、SARADC、ETH2 等继续按 M7.0 分配表实施。
