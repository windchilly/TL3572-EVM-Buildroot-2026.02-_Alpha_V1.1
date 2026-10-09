# UP1/FD1 ↔ UP2/FD3：CAN FD / BRS 实机验证

2026-10-09，板卡 `192.168.2.141`，M6 openEuler 运行镜像，UP1=CPU4、UP2=CPU5。
四轮 CAN FD 测试全部 PASS：不变速、BRS 约 2 Mbit/s、BRS 约 4 Mbit/s，以及
4 Mbit/s 档加 Linux CPU 负载/逆序停止。每轮每路 TX/RX 各 3000，覆盖 16/32/64 字节，
四轮每路累计 TX/RX 各 12000、有效载荷各 448000 字节；错误、溢出及错误核心中断为 0。
随后用未修改的经典 CAN IRQ 固件再通过 10000 次请求/应答和完整回收，无需重启。

本报告证明两个端口的 FD/BRS 中断数据面切片，不等于四口、错误恢复、实时性、
持久 DT/冷启动或 M7.0 完整验收。原经典 CAN 记录/固件保留，不回写其证据。

## 接线、所有权与实现

沿用用户确认的 FD1↔FD3 接线：H↔H、L↔L、共地，两端终端电阻（J9/J13）。
禁止同一接口 H/L 互短；仅隔离测试总线，不接真实执行器。
UP1 直接控制 CAN1 `0x2ab10000`、INTID185、MPIDR=`0x100`、target=`0x10`；
UP2 直接控制 CAN3 `0x2ab30000`、INTID187、MPIDR=`0x101`、target=`0x20`。
CRU/IOC 地址、位级 mask 和最小 MMU 页沿用已测的
[自主初始化/IRQ 方案](../can-irq-20261009/README.md#接线资源与实现)。
CRU/GIC 是共享物理页，软件字段约束不是硬件位级防火墙。

每轮先确认两 CPU OFF、Linux CAN DOWN，解绑 CAN1/CAN3，故意关自己的 gate、保持
reset 并置 divider=/16。各 UP 自行恢复 /4、gate/reset/mux，初始化 FD 控制器并严格
读回 NBTP/DBTP/TDCR/BRS_CFG，再收发。本轮不执行 Linux bitrate/up 初始化。
共享 GPLL/父级总线和 M6 平台启动仍由系统准备；pinmux 没有先故意置错。
Linux 与 RPMsg 只负责启停、读日志，不代理 CAN 帧；仅本核 ISR 消耗 RX FIFO。

新 [FD 源码](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_fd_test.c)
独立于原经典 CAN 源码；[编解码头](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_fd_codec.h)
保存 DLC/标志/小端字转换及位时序常量，
[0004 补丁](../../../source/patches/uniproton/0004-rk3572-can-fd-test-hook.patch)
增加默认关闭的 `M7_CAN_FD_TEST`，不改变已有默认模式。
标准数据帧：UP1 请求 ID=`0x321`，UP2 应答 ID=`0x456`，单请求在途。
每阶段 1000 次请求/应答，长度依次为 16/32/64；校验序号、profile 和全部有效载荷，
接收原始头必须符合 FDF、BRS、DLC，拒绝 EFF/RTR。RX FIFO 固定读取 18 个 word，
其中 16 个数据 word 支持 64 字节。发送使用有界自动重试（配置 100 次），
但未注入错误测试重试/恢复，不能视为生产用队列或 bus-off 恢复驱动。

## 位时序与来源边界

本轮 baudclk=GPLL 1188 MHz /4 =297 MHz；下表速率是**按时钟与寄存器计算值**，
不是示波器测量值，也不证明与独立厂商对端互操作。
仲裁 NBTP=`0x0c020c54`：BRP=6、TSEG1=85、TSEG2=13，总 99 TQ，
500000 bit/s，采样点约 86.87%。BRS 数据相位 TSEG1=27、TSEG2=9，总 37 TQ，
采样点约 75.68%；约 2/4 Mbit/s 档相对整数目标偏差均 +0.338%。

| profile | BRS | 线上仲裁 / 数据速率 | DBTP | TDCR | BRS_CFG |
|---|---|---|---|---|---|
| 0 | 关 | 500000 / 500000 bit/s | `0x0d90031a`（预置，不切速率） | `0x0` | `0x7` |
| 2 | 开 | 500000 / 2006756.76 bit/s | `0x0d90031a`，BRP=4 | `0x0` | `0x7` |
| 4 | 开 | 500000 / 4013513.51 bit/s | `0x0d90011a`，BRP=2 | `0x35`（enable，offset=26） | `0x7` |

参考仓库中 Stage06 完整厂商内核的 `rk3576_can.c` 与 `rockchip_canfd*` 寄存器定义、
[Rockchip CAN FD 指南 V1.3.0](../../../../../docs/reference/rockchip/en/Common/CAN/Rockchip_Developer_Guide_CAN_FD_EN.pdf)
第 5、7–10 页，以及 Rockchip 作者的
[2024-12 驱动补丁](https://lists.infradead.org/pipermail/linux-rockchip/2024-December/053628.html)
（FDF/BRS、DBTP 和 TDC）与
[2025-11 修订补丁](https://lists.openwall.net/linux-kernel/2025/11/12/215)
（接收格式和 18-word FIFO）。指南覆盖 RK3576 等，不是 RK3572 专用 TRM；
较新补丁还带 RK3576 CAN FD 限制，不能直接据其推出 RK3572 的可用性。
本实现对 RK3572 的兼容判断来自已有寄存器映射，**再由本板读回及两个 UP 的物理收发验证**；
保留本平台 TX 请求位 `1<<16`，不照搬其他 SoC 的 CRU 或触发位。

## 实机结果与退出

| 原始记录 | 条件 / 停止顺序 | 每路 TX/RX | 每路 IRQ / TXIRQ / RXIRQ | 结果 |
|---|---|---|---|---|
| [run-01-fd0.log](run-01-fd0.log) | FD、不变速；B→A | 3000 / 3000 | 6000 / 3000 / 3000 | PASS |
| [run-02-fd2.log](run-02-fd2.log) | FD、BRS 约 2 Mbit/s；B→A | 3000 / 3000 | 6000 / 3000 / 3000 | PASS |
| [run-03-fd4.log](run-03-fd4.log) | FD、BRS 约 4 Mbit/s；B→A | 3000 / 3000 | 6000 / 3000 / 3000 | PASS |
| [run-04-fd4-cpu-load.log](run-04-fd4-cpu-load.log) | 同上，四个 nice=19 Linux worker；A→B | 3000 / 3000 | 6000 / 3000 / 3000 | PASS；worker 回收 |
| [run-05-classic-rollback.log](run-05-classic-rollback.log) | 原经典 CAN IRQ ELF，8 字节；B→A | 10000 / 10000 | 20000 / 10000 / 10000 | PASS；不计入 FD 累计 |

以上都按 B→A 启动。FD 每路每轮 txbytes/rxbytes=112000、rxfd=3000；
profile0 rxbrs=0，其余 rxbrs=3000；四轮每路 rxfd=12000、rxbrs=9000。
16/32/64 字节 RX 原始头的 DLC 分别为 10/13/15，FDF=1、BRS 与 profile 一致。
`rxirq` 统计 ISR 消耗帧数，本轮每帧一个 watermark；没有把帧数当作通用 IRQ 次数定义。
所有轮次控制器 TXERR/RXERR、IRQ error flags、overflow、wrongcpu 都为 0。
四个低优先级 worker 不代表全核饱和；未测硬实时期限、时延或抖动。

每轮退出 UP 自行关 CAN 中断、复位模式、禁用 SPI/清 pending、恢复路由。
宿主确认 CPU4/5 PSCI OFF，然后核验 SPI disabled、pending/active=0、target=1，
才恢复保存的 own CRU/IOC 字段，核对其余 CAN 位不变并重新绑定 Linux。
每轮数据面 `OVERALL PASS` 和 `CLEANUP PASS` 均成立。`micad` PID311、active、
NRestarts=0 始终不变，未复现双停止 SIGABRT；不覆盖已知的全局 `mcs_fd` create/rm 泄漏。

[最终状态](final-board-state.log) 和 [资源快照](final-resource-snapshot.json) 确认
原 `up-a/up-b` Offline、CPU4/5 OFF、四 CAN 绑定 `rk3576_can` 且 DOWN、
ETH1/Linux eth0 UP、SSH 正常、failed units=0。
boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7` 与实施前一致，无重启/刷机，
原 M6 ELF/配置/DT 未覆盖。快照的 `owner` 是规划，`not_verified` 是只读脚本自身的边界，
不否定在线测试证据；Linux 重绑后重新使能自己的 IRQ 是预期状态。

## 构建、复现与校验

主仓库父提交 `077f93b1407ede86363ef89753ff6c50ddc26523` 加本次跟踪输入。
实际在 `10.100.60.226` 的 `dev_openeuler`、
`/home/openeuler/build/tl3572-2oo3`、Arm GNU 14.3.Rel1 / GCC 14.3.1 构建。
实测树 `src/UniProton-m7-can-fd-20261009`；
第二树 `src/UniProton-m7-can-fd-repro-20261009` 重新复制完整 M6 基线、
顺序应用 0001/0002/0003/0004 并覆盖源码，在六个新的应用 CMake 目录重新编译。
**复用已完成的 M6 库，本轮没有再次空目录重建全部库/Yocto。**
六对 `objcopy -O binary` 运行镜像逐字节一致，整 ELF 因调试路径不同 hash 不同。
日志：[首次/profile0](build-first.log)、[profile2/4](build-more.log)、[第二树/逐字节比较](build-repro.log)。
基线 libc/proxy、CMake 未使用变量和 RWX LOAD warning 保留，不能称为无 warning 构建。

换机所需完整源码/工具链已在 `repro-inputs/` 与 `software/toolchains/`；
先按 [RK3572 空目录入口](../../../../../repro-inputs/rk3572/README.md) 的 `m6-up`
从源码生成 M6 库，再用 [M7 FD 构建入口](../../../build/README.md#can-fd--brs-模式2026-10-09)
准备新树并构建 profile0/2/4。9 月固定 Stage07 tar 不回写，不能只拿该历史包复建本功能。
原 IRQ 切片的历史 SHA256SUMS 应在提交 `077f93b` 核验，其中可变文档/总固件清单已更新；
本轮另立 [SHA256SUMS](SHA256SUMS)，路径相对本目录。
六份实测 ELF 保存在 [firmware](../../../firmware/)，精确 SHA256 见
[固件清单](../../../firmware/SHA256SUMS) 和最终状态日志。

本地 Python 单测 21/21 PASS（含原有 17 项和新增 4 项 FD 结果校验）。
本地检查及构建机/板端与仓库的 24 文件 hash 对照见 [validation.log](validation.log)。
原生 C 编译 `gcc -std=c11 -O2 -Wall -Wextra -Werror tests/test_can_fd_codec.c` 并执行 PASS，
覆盖精确 DLC、FDF/BRS/EFF/RTR、64 字节 pack/unpack、NBTP/DBTP/TDC 编码。
0004 顺序补丁检查、Bash/Python 语法与文件校验通过。
执行器拒绝不完整 stage/错误标志/错误计数/错误配置/相同核 target；经典 CAN PASS 不足以通过 FD 校验。

## 仍待验证 / 下一步

1. FD2↔FD4 先逐口确认丝印映射，再重复经典 CAN、IRQ、FD/BRS；需用户调整接线后确认。
2. 独立外部 CAN FD 对端、错误/断线/bus-off 恢复、单边重启、四路并发、长时负载。
3. 持久 M7 DT/启动所有权、未知 pinmux/冷启动与回退；共享根资源仍需系统级管理。
4. 外部仪器验证位速率与时延/抖动；UART/SARADC/ETH2 按 M7.0 表继续实施。
