# UP1 / SoC UART1 ↔ UP2 / SoC UART2：隔离半双工 RS-485 直驱

2026-10-09，TL3572 `192.168.2.141`，M6 openEuler；用户确认“485已对接”后测试。
保持既定控制器分配：UP1=CPU4/UART1/ttyS1，UP2=CPU5/UART2/ttyS2。
只用两路隔离对接，不接真实执行器；原 M6、DT、CAN、RS-232 源码/固件不覆盖。

## 接线、编号与方向

按 [评估板测试手册](../../../../../docs/manuals/2-1-评估板测试手册.pdf) 第50–53页表6：
板上 UART1/A1/B1 对应 ttyS2/SoC UART2、GPIO78、J6；
板上 UART2/A2/B2 对应 ttyS1/SoC UART1、GPIO27、J5。
因此按手册板上 UART2 属 UP1，板上 UART1 属 UP2，不能把丝印序号直接当 SoC 序号。
[原理图](../../../../../hardware/carrier-board/TL3572-EVM评估底板原理图/TL3572-EVM-A1.1-000-SCH-202609021543.pdf)
第11页的 A1/B1、A2/B2 **电气网名**又分别连接 SoC UART1/UART2；
应区分这两种编号系统。本次两口成对测试确认链路，不单独证明每个物理端子的丝印映射。

用户接线按 A↔A、B↔B、隔离侧参考地相连理解；不是 A/B 短接，不是 RS-232 TX/RX 交叉。
原理图 J7-1/4 为 GNDI1，J7-2/3、5/6 各为一对 B/A。
J5/J6 提供120Ω端接；本次未测量端接电阻，也未独立确认跳帽状态。

U24/U27 为 [CA-IS3082WX](../../../../../hardware/datasheets/评估底板元器件/RS-485/CA-IS3082WX.pdf)，
半双工器件；RE(active-low) 与 DE(active-high) 同接 RTSN。
物理 RTSN 高=TX/禁RX，低=RX/禁TX；板上方向输入有10k上拉。
MCR.RTS 是输出反相信号，故 **MCR=0→TX，MCR=2→RX**。
语义参考 Linux 官方 [serial_reg.h](https://github.com/torvalds/linux/blob/master/include/uapi/linux/serial_reg.h)。
本实现手动控制 UART MCR.RTS，**不是已验证的自动 RTS/CTS 换向**，不读写 GPIO bank。

## 资源划分

| 资源 | UP1 / CPU4 | UP2 / CPU5 |
|---|---|---|
| SoC UART / Linux / 手册板号 | UART1 / ttyS1 / UART2 | UART2 / ttyS2 / UART1 |
| MMIO / SPI / INTID | `0x26500000` / 125 / 157 | `0x2c140000` / 126 / 158 |
| MPIDR / 实测GIC target | `0x100` / `0x10` | `0x101` / `0x20` |
| PCLK gate/reset/mask | `0x260b0814`/`0x260b0a14`/`0x80` | `0x26090838`/`0x26090a38`/`0x20` |
| SCLK gate/reset/mask | 同PMU寄存器 / `0x40` | `0x2609083c`/`0x26090a3c`/`0x1` |
| 时钟选择 / mask/value | `0x260b0320` / `0x3`/`0x1`，直选xin24m | `0x26090420` / `0x7ff`/`0x300`，xin24m/div1 |
| TX / RX / RTSN引脚 | GPIO0_C0 / B7 / D3 | GPIO2_B4 / B5 / B6 |
| TX / RX IOC mask/value | `0x26074010` `0xf/0x9`；`0x2607400c` `0xf000/0x9000` | `0x2608404c` `0xff/0x99` |
| RTSN IOC mask/value | `0x26074018` `0xf000/0x9000` (mux9) | `0x2608404c` `0xf00/0xc00` (mux12) |

位定义取自归档的 Stage06 RK3572 内核 `clk-rk3572.c`、`rst-rk3572.c`、
`pinctrl-rockchip.c`；UART regshift2/regwidth4。UART1不触碰未使用的主域UART1父时钟。
MMU仅增加本实例UART、CRU/PMUCRU、IOC各4KiB和GIC16KiB；没有映射GPIO bank。
软件位掩码不是共享CRU/IOC/GIC页的硬件位级防火墙。

## 实现与安全退出

新增独立 [驱动](../../../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_rs485_test.c)、
[0006钩子](../../../source/patches/uniproton/0006-rk3572-rs485-test-hook.patch)、准备/构建入口及执行器；
共用原RS-232的32字节CRC codec，不修改已经通过的RS-232实现。
`M7_RS485_TEST` 默认OFF，与CAN/RS-232模式互斥；六配置均AutoBoot=no。

Linux先检查两CPU OFF、原实例Offline、无串口进程、非console、方向脚无GPIO/mux申请者，
再临时解绑UART1/2。不open/stty/TX/RX、不export GPIO、不代理数据或运行时方向。
保存资源后故意关own gate/保持reset；UART1选择RC oscillator，UART2选择xin24m/div16。
UP自行恢复时钟/复位/分频、TX/RX mux、DLL/DLH/8N1/FIFO，并先设MCR=2再接RTSN mux。

RX字节仅由ISR读RBR，TX字节仅由ISR写THR（每THRE一个字节）；任务用128字节软件RX环。
每帧发送前等待4 ticks换向保护，切TX后等1 tick，再通过TX IRQ发送。
任务检查TEMT（包含最后一个停止位），才禁TX IRQ、清RX FIFO、切RX并开RX/line IRQ。
发送时RX关闭，不把回显当对端应答；采用单请求在途、A请求/B应答、序号/全帧CRC校验。
日志核验每路1000次TX、1002次RX设置（初始、1000次发送后、最终清理）、MCR最终2。
`guardticks=4`不是外部仪器测得的换向时间；未验收极限保护间隔或抖动。

UP退出前IER=0、MCR=2、清FIFO、禁SPI/清pending、恢复target/priority。
执行器停止两实例，**确认CPU4/5 PSCI OFF后**才恢复原CRU/IOC/GIC并重绑Linux，
比较其他UART与共享GIC邻接字段；OFF未确认则不恢复、不重绑、不自动重启。
Linux原方向mux恢复后可能回到GPIO输入/上拉TX，不能将测试结束RX状态称为持久安全态。
UART0救援口/ETH1管理口不操作，日志通过两独立保留内存环读取。

## 实机结果

| 原始记录 | 标称波特率 / 条件 | 停止顺序 | 每路TX/RX | 结果 |
|---|---|---|---|---|
| [run-01-115200.log](run-01-115200.log) | 115200 / 8N1 | B→A | 1000/1000 | PASS |
| [run-02-38400.log](run-02-38400.log) | 38400 / 8N1 | B→A | 1000/1000 | PASS |
| [run-03-9600.log](run-03-9600.log) | 9600 / 8N1 | B→A | 1000/1000 | PASS |
| [run-04-cpu-load.log](run-04-cpu-load.log) | 115200 / 四个nice19 Linux worker | B→A | 1000/1000 | PASS，worker回收 |
| [run-05-reverse-stop.log](run-05-reverse-stop.log) | 115200 / 逆序停止 | A→B | 1000/1000 | PASS |

每轮均B→A启动，每路IRQ=64000、TXIRQ=33000、RXIRQ=32000，TX/RX各32000字节；
line error/overflow/wrongcpu/busy/storm/direction error均0，序号/全帧CRC正确。
TXIRQ包含最后一个FIFO空事件，IRQ cause次数与GIC入口数不是同一个量。
累计每路TX/RX各5000帧/160000字节；每路5000次TX、5010次RX设置，五轮均同时
`OVERALL PASS`、`RESOURCE RESTORE PASS`、`CLEANUP PASS`。
四个低优先级worker不是全核饱和，不证明硬实时、时延或抖动。

24MHz/整数UART除数13/39/156的计算速率约115384.62/38461.54/9615.38 bit/s，
比标称高约0.1603%，不是外部测量值。器件500kbit/s上限不代表本轮测试到该上限。

[最终状态](final-board-state.log)、[最终资源](final-resource-snapshot.json)与
[只读预检](resources-before.json)确认两原实例Offline、CPU4/5 OFF、UART1/2重绑Linux，
own CRU/IOC/GIC及保护字段一致，方向脚恢复未申请状态，UART4/8和四CAN仍绑定Linux，
四CAN均DOWN、systemd failed=0、ETH1/eth0正常；micad PID311/active/NRestarts0。
boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7`未变，无重启/刷写，原M6/DT未改。
没有再现双停止SIGABRT；已知另一处全局`mcs_fd` create/rm泄漏仍未修复。

## 构建与复现

父提交 `c0e08ae4805b328df3c5a2aacc060eb75d0b83b4` 加本轮跟踪补丁/覆盖层。
构建机`10.100.60.226`，容器`dev_openeuler`，Arm GNU14.3.Rel1/GCC14.3.1。
主树`src/UniProton-m7-rs485-20261009`；第二树`src/UniProton-m7-rs485-repro-20261009`。
从完整M6基线复制，应用0001/0002/0003/0005/0006；不应用CAN FD的0004。
两树各重编六应用，六对`objcopy -O binary`运行镜像逐字节一致，ELF调试路径不同。
**本轮复用M6库，不是再次从空目录全量重建库/内核/Yocto。**
换机先按 [空目录全源码入口](../../../../../repro-inputs/rk3572/README.md)准备固定Docker摘要、
LFS输入并运行`run.sh prepare`、`run.sh m6-up`生成库，再用
[RS-485构建说明](../../../build/README.md#up1--up2-rs-485-直驱测试固件2026-10-09)。
历史Stage07 tar不回写，应使用包含本报告的当前提交。

[build-first.log](build-first.log)为实测115200固件构建；[build-more.log](build-more.log)为38400/9600；
[build-repro.log](build-repro.log)为第二树编译与六次cmp；
[build-inputs.log](build-inputs.log)记录工具链、M6库hash与运行镜像hash。
基线libc/proxy、CMake未用CPU_TYPE、RWX LOAD警告仍存在，不称无warning构建。
六ELF hash见 [固件清单](../../../firmware/SHA256SUMS)。

Python31项单测（原26+新增5）通过；共享codec原生C `-Wall -Wextra -Werror`检查
标准CRC向量、1000序号、错误角色/序号与256000个bit翻转；Bash/补丁/Python语法和保存日志重验
见 [validation.log](validation.log)；保存证据重验器为
[verify_rs485_records.py](../../verify_rs485_records.py)，切片清单见 [SHA256SUMS](SHA256SUMS)。
旧RS-232清单涉及可变文件，应在固定提交`c0e08ae`校验；不回写历史证据。

仍未验收独立外部RS-485对端、Modbus等业务协议、断线/短路恢复、任意时刻停止、
长时压力/实时性、持久DT、未知pinmux冷启动。晶振/父级总线/电气pinctrl仍由系统提供。
CAN FD2/FD4仍为用户选择的SKIPPED/未验证；本轮不代表全M7.0验收。
