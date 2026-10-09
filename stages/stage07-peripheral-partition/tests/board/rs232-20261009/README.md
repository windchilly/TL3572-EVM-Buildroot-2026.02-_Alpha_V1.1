# UP1 / 板上 UART4 ↔ UP2 / 板上 UART3：RS-232 直驱测试

2026-10-09，TL3572 `192.168.2.141`，M6 openEuler 运行镜像。
UP1=CPU4/SoC UART4/ttyS4；UP2=CPU5/**SoC UART8/ttyS8，板上标 UART3**。
用户确认交叉线已接好后实施。未使用 Linux 串口数据代理，未刷写或重启。

## 接线与资源

同一 J4 六位端子：J4-1/T4 → J4-5/R3，J4-4/T3 → J4-2/R4。
J4-3、J4-6 为板上共地；不是 TTL，也不是 RS-485 A/B。
依据 [底板原理图](../../../../../hardware/carrier-board/TL3572-EVM评估底板原理图/TL3572-EVM-A1.1-000-SCH-202609021543.pdf)
第 11 页 U23/SIT3232EEUE 与 [评估板测试手册](../../../../../docs/manuals/2-1-评估板测试手册.pdf)
第 47 页表 5，结合 [生效 DTS](../tl3572-live-m6-20260928.dts)。仅隔离测试，不接真实执行器。

| 资源 | UP1 / CPU4 | UP2 / CPU5 |
|---|---|---|
| 板上丝印 / 控制器 | UART4/T4/R4 / UART4 | UART3/T3/R3 / UART8 |
| UART MMIO / SPI / INTID | `0x2c160000` / 128 / 160 | `0x2c1a0000` / 132 / 164 |
| MPIDR / 实测 GIC target | `0x100` / `0x10` | `0x101` / `0x20` |
| PCLK gate/reset / mask | `0x26090838`/`0x26090a38` / `0x80` | 同寄存器 / `0x800` |
| SCLK gate/reset / mask | `0x2609083c`/`0x26090a3c` / `0x40` | `0x26090840`/`0x26090a40` / `0x4` |
| 源/分频字段 / mask/value | `0x26090428` / `0x7ff`/`0x300` | `0x26090438` / `0x7ff`/`0x300` |
| TX/RX 引脚 / mux | GPIO0_B5/B4，mux9 | GPIO0_C2/C1，mux9 |
| IOC mux / mask/value | `0x2607400c` / `0xff`/`0x99` | `0x26074010` / `0xff0`/`0x990` |

地址/位定义来自已归档 Stage06 完整内核的 `clk-rk3572.c`、`rst-rk3572.c`、
`pinctrl-rockchip.c`，不套用 RK3576 表。UART reg-shift=2、reg-io-width=4。
IRQ 寄存器语义另参考 Linux 官方 [serial_reg.h](https://github.com/torvalds/linux/blob/master/include/uapi/linux/serial_reg.h)
和 [8250_dw.c](https://github.com/torvalds/linux/blob/master/drivers/tty/serial/8250/8250_dw.c)。

## 实现与退出规则

[UART C](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_rs232_test.c)
及 [codec](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_rs232_codec.h)
为独立默认关闭测试模式。Linux 先检查串口无用户、非 console、两 CPU OFF，再解绑
`dw-apb-uart`。不执行 stty/open/TX/RX 初始化；故意关 own 时钟、保持复位、置分频/16。
各 UP 自行恢复时钟/复位/分频1、写 own mux、配置 DLL/DLH/FIFO/8N1，并注册本核 SPI。

数据只能由 ISR 读 RBR/写 THR。RX 用 128 字节软件环；TX 每个 THRE 写一个字节，
不假设 FIFO 深度。任务只操作软件队列及检查 TEMT/错误状态。
固定 32 字节帧包含角色、序号、确定性载荷、CRC-16/CCITT-FALSE，单请求在途、1000 次。
CRC 已用标准 `123456789` → `0x29b1` 核验；接收比较整帧，包括序号与 CRC。

UP 测试结束先关 IER、清 FIFO、禁用 SPI/清 pending、恢复 own target/priority。
执行器停止两临时实例，确认 CPU4/5 PSCI OFF 后才恢复 own CRU/IOC 状态并重绑 Linux。
同时比较其他 UART/共享 GIC 邻接字段；CPU OFF 未确认时禁止恢复/rebind，不自动重启。
原 M6/DT/已有 CAN 固件保留，UART0/ETH1 管理口不操作，日志仍走两个独立内存环。

## 测量边界

使用 xin24m=24 MHz、source selector3、CRU divider1。
标称 115200/38400/9600 对应 UART 除数 13/39/156；计算速率分别约
115384.62/38461.54/9615.38 bit/s，误差均 +0.1603%，**不是外部仪器测量值**。
只测试 8N1、32 字节请求/应答，不证明最大吞吐、同时持续全双工或工业协议。
共享根总线/晶振、启动期 pinctrl 的电气属性仍由平台准备；mux 未故意置错。
最小 MMU 映射只增加 own UART、CRU、GPIO0 IOC 的各一页和 16 KiB GIC；
共享页软件字段约束不是硬件位级隔离。持久 DT、未知 pinmux 冷启动、断线恢复、
独立外部 RS-232 对端、长时负载/实时性尚未测，不是 M7.0 完整验收。

## 实机结果

| 原始记录 | 标称波特率 / 条件 | 停止顺序 | 每路 TX/RX | 结果 |
|---|---|---|---|---|
| [run-02-115200.log](run-02-115200.log) | 115200 / 8N1 | B→A | 1000/1000 | PASS |
| [run-03-38400.log](run-03-38400.log) | 38400 / 8N1 | B→A | 1000/1000 | PASS |
| [run-04-9600.log](run-04-9600.log) | 9600 / 8N1 | B→A | 1000/1000 | PASS |
| [run-05-cpu-load.log](run-05-cpu-load.log) | 115200 / 四个 nice=19 Linux worker | B→A | 1000/1000 | PASS，worker 回收 |
| [run-06-reverse-stop.log](run-06-reverse-stop.log) | 115200 / 反向停止 | A→B | 1000/1000 | PASS |

每轮均 B→A 启动，两个实例各 IRQ=64000、TXIRQ=33000、RXIRQ=32000，
TX/RX 各 32000 字节，line error、overflow、wrongcpu、busy、storm 全为 0。
TXIRQ 包括最后一个 FIFO 空事件，IRQ cause 次数与 GIC 入口数不是同一个量。
累计每路 TX/RX 各 5000 帧/160000 字节；五轮 `OVERALL PASS` 与 `CLEANUP PASS` 同时成立。
四个低优先级 worker 不是全核饱和，不证明硬实时、时延或抖动。

[最终状态](final-board-state.log) 与 [资源快照](final-resource-snapshot.json) 确认
两原实例 Offline、CPU4/5 OFF、UART4/8 重绑 `dw-apb-uart`、四 CAN 绑定且 DOWN、
ETH1/eth0 UP、systemd failed=0，micad PID311、active、NRestarts=0。
boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7` 未变，无重启/刷写；本轮不修改 M6/DT。
[只读预检](preflight.json) 与最终快照的 own CRU/IOC/GIC 字段一致。
没有复现双停止 SIGABRT；已知另一处全局 `mcs_fd` create/rm 泄漏仍未修复。

## 构建与复现

父提交 `22e80f485a2943090db9dd3e2b71b76b062b6ab8` 加本轮跟踪内容。
构建机 `10.100.60.226`、`dev_openeuler`、Arm GNU 14.3.Rel1 / GCC 14.3.1。
主树 `src/UniProton-m7-rs232-20261009`；第二树 `src/UniProton-m7-rs232-repro-20261009`。
二者从完整 M6 基线复制，应用 0001/0002/0003/0005，不应用 CAN FD 的 0004。
两树重新编译六应用，六对 `objcopy -O binary` 运行镜像逐字节一致；ELF 调试路径不同。
**本轮复用 M6 库，不是再次从空目录全量重建库/内核/Yocto。**
完整源码和工具链已有归档；换机先用 M6 全源码入口 `m6-up` 生成库，再用
[RS-232 准备/构建入口](../../../build/README.md#up1--up2-rs-232-直驱测试固件2026-10-09)。
历史 Stage07 tar 不回写；需包含本报告的当前提交与 LFS 输入。

[build-first.log](build-first.log) 是未部署的初次编译；随后为避免任务与 ISR 的错误状态更新竞争，
增加短 HwiLock 后生成实际部署版，见 [build-final.log](build-final.log)。
[build-repro.log](build-repro.log) 包含六对运行镜像比较和 M6 库 hash。
基线 libc/proxy、CMake 未用 CPU_TYPE、RWX LOAD warning 仍存在，不称为无 warning 构建。
实测六 ELF 的完整 hash 见 [固件清单](../../../firmware/SHA256SUMS)。

Python 单测 26/26（原 21 + 新 UART 5）通过；原生 C `-Wall -Wextra -Werror`
codec 测试覆盖 CRC 标准向量、1000 序号、错误角色/序号和 256000 个单 bit 翻转。
0005 补丁顺序检查、Bash/Python 语法、六 ELF 与板端 hash、保存日志的结果重验通过，
检查输出见 [validation.log](validation.log)，切片输入/证据清单见 [SHA256SUMS](SHA256SUMS)。
历史 CAN FD 清单含可变的构建说明/固件总清单，应在其固定提交 `22e80f4` 校验；
本轮另立清单，不改历史原始证据。

首轮执行器仅在只读预检失败：Linux 6.12 串口核心多了一层 serial-port 子目录，
旧末级目录名判断不适用。改为核验精确平台控制器的祖先路径后才实际测试；
[run-01-115200.log](run-01-115200.log) 保留，不计入成功轮次，未解绑或发送字节。

CAN FD2/FD4 按用户要求本轮跳过，仍为 **SKIPPED / 未验证**，不能由 FD1/FD3 结果推为 PASS。
下一项是 RS-485 两口；先核对各自方向控制、资源及接线，用户确认后才进行发送测试。
