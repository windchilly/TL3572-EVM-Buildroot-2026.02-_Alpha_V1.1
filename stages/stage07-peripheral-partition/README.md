# Stage 07 / M7.0：全资源划分与外设直驱

当前状态：`IN PROGRESS / 全资源目标已规划 / 日志首切片实机验证 / UP1↔UP2 CAN、RS-232/485 自主配置及 IRQ 收发切片通过 / 持久外设移交尚未完成 / M7.0 未验收`。

2026-10-10 最新[P3c定时器实测](tests/powerlink-timer-p3c-20261010/README.md)：仅临时UP2，CNTP/PPI30真实72IRQ/72任务回调及退出通过。
修正NS视图IGROUPR读零误判；样本最大IRQ29.292us、任务89.75us，非工业最坏时延/100us周期承诺。
12probe+3mailbox原生、99Python及累计双新树复编通过；正式M6/DT/两ELF未改，无PHY/ETH/CAN/UART帧/重启。
结束两UP Offline/CPU OFF、Linux绑定/地址/路由/micad/boot不变；下一步半双工与安全停机，MN/CN仍未验收。

2026-10-10 最新 [P3b累计候选软件接入](tests/powerlink-mn-p3b-20261010/README.md)：
UP2新增休眠owner/单槽邮箱/跨任务快照，仅软件env-init/env-exit/status；UP1拒绝PLK命令。
596个完整核心/OD/port/BSP函数保留，最终ELF未解析为零；12组C、92项Python与双目录11产物一致。
默认不初始化栈/PHY/timer、不启动MN、不发帧。候选两ELF单独归档，正式两ELF和板卡均未改。
旧M6/libmetal的125条FP/SIMD保留且逐点比对，无新增；不能称整个ELF无FPU，详见记录。

此前 [P3a被动完整栈软件接入](tests/powerlink-mn-p3a-20261010/README.md)：
真实OD/内存CDC/单owner生命周期、停止失败保留资源、四请求队列错误传播已实现；
100次被动启停、25组完整栈C、87项Python通过，77个C强制合并与双目录9产物一致。
该轮尚无RTOS常驻任务/命令/累计ELF；本轮在上述P3b补齐被动软件入口，运行节点仍未验收。

2026-10-10 POWERLINK 增量：用户确认 UP2 做 MN 主站，通过 ETH2 控制外部设备。
已完成完整上游源码固定、AArch64 可移植核心构建、无硬件 NMT/OD 检查及独立复编；
不等于可运行主站或板端验收，正式累计 ELF 未替换。见[开发路线](docs/m7.0-powerlink-mn-roadmap.md)
和[P0 软件证据](tests/powerlink-mn-p0-20261010/README.md)。

同日继续完成 [P1 EDRV 软件基线](tests/powerlink-mn-p1-20261010/README.md)：
独立 DMA 缓冲池、持续轮询收发/回调/组播/过滤/安全停止及 forced 100-half BSP 已编译；
9 组 EDRV C 和73项 Python 回归通过、两全新目录复编一致。
该轮半双工未上板，MN/高精度 timer 未接入；只生成休眠的累计候选，正式两 ELF 不变。

随后 [P2 RTOS/高精度定时软件基线](tests/powerlink-mn-p2-20261010/README.md)完成：
target/缓存/双逻辑定时器和真实 UP2 CNTP/PPI30 BSP 已编译；12 组 C 与79项 Python 通过，
两独立目录 9 个产物逐字节一致，页表仍9/16、10/16。IRQ 只记录到期，回调由同一 owner 任务执行。
尚无 MN 运行命令、定时器硬件/精度或半双工验收；本轮正式两 ELF/板卡不变，下一步 P3 passive 接入。

2026-10-10 最新：UP2 ETH2直驱100M轮询DMA L2切片通过，新增到同一套累计UP1/UP2两ELF。
COM7/115200已实际抓取；用户人工重启后V3共享电源/根时钟防护、PHY探测和三轮物理收发通过，
64/1514B每方向累计6000帧全载荷/序号/CRC正确，覆盖Linux负载及两种停止顺序。
每轮DMA复位后双CPU OFF、Linux ETH2/3恢复，ETH1/micad/boot不变，CAN/UART仍不发送。
两全新源码树运行镜像与实测版一致；IRQ/IP/拔插恢复/持久DT/冷启动及完整M7.0未验收。
正式累计两ELF已更新，历史MMU版本从e1add984恢复；见[ETH2直驱与复现](tests/board/eth-direct-20261010/README.md)。
下面较早的“ETH2未实现/未重启”仅对应历史轮次，不能覆盖此次结果。

2026-10-09 最新实机结果：ETH3专用U21/P02电源初始化已修，SR9900枚举为Linux eth2，
与ETH2/eth1协商100M全双工，两轮Linux物理L2每方向累计4000帧完整校验通过。
开机电源服务已安装/启用并执行成功，重复启动幂等；未重启验证，首次通电有下游USB重枚举。
ETH2的UP2直驱仍未实现/未验收，现有两UP统一ELF未改，CAN/UART发送仍暂停。
见[ETH3恢复与物理对端基线](tests/board/eth3-recovery-20261009/README.md)。

2026-10-09 最新实机结果：已修复统一目标页表32→64KiB及启动返回值检查，
修复后的两份正式统一ELF通过四轮被动双实例回归，两种启动/停止顺序、每路400次虚拟echo，
SCTLR.M=1且全部48个实际PTE完整。构建后强制预算与CBNZ错误分支核验，两新树运行镜像一致。
用户明确“接线已改变，先不要发送”，所有工业收发仍暂停、Linux绑定未动，
结束CPU4/5 OFF、原实例Offline、micad未重启。见[MMU修复与回归](tests/board/integrated-mmu-fix-20261009/README.md)。
修复前两次正式失败及仅加打印掩盖异常的诊断证据不回写，见[原故障记录](tests/board/integrated-passive-20261009/README.md)。

2026-10-09 新的后续要求：转为 [统一固件、增量集成](docs/m7.0-incremental-firmware-policy.md)，
每版本UP1/UP2各一份集成ELF，同一固件内做单项/组合/并发回归，不再为各接口更换测试固件。
已合并CAN经典/FD/BRS、RS-232、RS-485和日志/诊断，生成两份被动启动、运行时配置的ELF。
两新目录复编运行镜像一致，17组无硬件原生检查、31项既有单测及ELF映射核验通过；
软件合并轮次当时未部署/上板；后续实机失败以顶部最新记录为准。见[统一固件软件记录](tests/board/integrated-20261009/README.md)。
历史单项证据保留；启动修复及无工业发送回归已完成，下一步须经重新接线确认继续物理集成测试。

2026-10-09 RS-485五轮通过：UP1/SoC UART1/CPU4 ↔ UP2/SoC UART2/CPU5，
115200/38400/9600 8N1，另测Linux负载和两种停止顺序，每路累计TX/RX各5000帧/160000字节，
错误为0。UP直接控制UART MCR/RTSN半双工换向、own clock/reset/mux及本核ISR收发，
无Linux GPIO/串口/RPMsg代理。按手册板上UART2属UP1、UART1属UP2；与SoC序号分开记录。
独立默认OFF模式、六ELF、两新源码树运行镜像逐字节一致，复用M6库；退出两CPU OFF、
UART1/2归还Linux、micad不重启，原M6/DT/CAN/RS-232保留。见
[RS-485实机记录](tests/board/rs485-20261009/README.md)。仍未持久DT/冷启动、独立外部对端、
工业协议/故障恢复/实时性验收。下一项先做SARADC资源、安全输入与消费者盘点。

2026-10-09 RS-232 五轮通过：板上 UART4（UP1/SoC UART4）↔板上 UART3
（UP2/SoC UART8），115200/38400/9600、8N1，另测 Linux CPU 负载和两种停止顺序。
每路累计 TX/RX 各 5000 帧/160000 字节，序号/CRC 和中断检查无错误；UP 自行初始化
own CRU/reset/mux，数据只由本核 ISR 收发。独立默认关闭模式、六份测试 ELF、
第二源码树运行镜像逐字节一致，复用 M6 库。退出两 CPU OFF、UART 归还 Linux、
micad 不重启，原 M6/DT 保留。见 [RS-232 实机记录](tests/board/rs232-20261009/README.md)。
仍未持久 DT/未知 pinmux 冷启动/工业协议验收。用户已选择跳过 CAN FD2/FD4，
两口保持 `SKIPPED / 未验证`，不从 FD1/FD3 推断 PASS；RS-485后续结果见上文。

2026-10-09 CAN FD/BRS 切片四轮通过：500 kbit/s 仲裁，数据不变速/约 2/4 Mbit/s，
16/32/64 字节逐帧全载荷校验。每路累计 TX/RX 各 12000，错误为 0；覆盖四个
低优先级 Linux CPU worker、两种停止顺序，再用原经典 CAN ELF 通过 10000 次请求/应答。
新增 FD 模式默认关闭，六份应用在第二棵新源码树复编，运行镜像逐字节一致；M6 库复用。
结束两 UP OFF/Offline、四 CAN Linux 绑定/DOWN、micad 不重启，原 M6/DT 不变。
源码、0004 补丁、六 ELF、构建/测试脚本与证据见
[CAN FD/BRS 实机记录](tests/board/can-fd-20261009/README.md)。尚未测 FD2/FD4、
独立外部对端、错误恢复/实时性或持久 DT/冷启动，不是全 CAN 或 M7.0 验收。

2026-10-09 新增默认关闭的 CAN IRQ 模式，Linux 解绑后故意关闭本实例时钟、保持
复位并改变分频，再由 UP1/CAN1/FD1 与 UP2/CAN3/FD3 自行初始化自己的字段、
接收各自 SPI。最终固件三轮每路 TX/RX=10000/10000、TXIRQ/RXIRQ=10000/10000，
错误/溢出/错误核心中断均为 0；覆盖四个低优先级 Linux CPU worker 和两种停止顺序。
UP 自行关中断/恢复路由，CPU4/5 OFF 后才恢复资源、重绑 Linux，micad 未重启。
两棵源码树重新编译的运行镜像逐字节一致。原 M6 固件/配置/DT 未覆盖，无刷机或重启。
见 [CAN 自主初始化与 IRQ 实机证据](tests/board/can-irq-20261009/README.md)。
共享 PLL/父级总线仍由系统准备；pinmux 未故意置错，冷启动、持久 DT
及 FD2/FD4 尚未验证，不能宣称完整 CAN 移交。FD/BRS 的后续验证见上文。

2026-09-28 已补齐 [GitHub 换机输入与构建入口](../../repro-inputs/rk3572/README.md)，
在空目录、固定基础容器中断网重建 M6 完整镜像、M6/M7 双固件、M7 MCS 软件包及
独立修复版 micad，均通过；四份固件和独立 micad 与实机版本逐字节一致。
见 [独立复现记录](../../repro-inputs/rk3572/tests/clean-rebuild.md)。这是现有软件切片的
可复建性验证，不是完整 M7 镜像或工业外设直驱验收，新产物未部署到板卡。

2026-09-28 已将 CAN FD1（Linux `can1`，M7.0 目标 UP1）与 CAN FD3
（Linux `can3`，M7.0 目标 UP2）组成物理总线完成经典 CAN 基线测试：每接口累计
收发各 10,640 帧、三轮 stop/start 恢复，错误/丢包/bus-off 均为 0。当前
`rk3576_can` 驱动拒绝启用 FD/BRS，因此当时 CAN FD 数据相位未验证。原始证据和边界见
[CAN FD1 ↔ CAN FD3 物理基线记录](tests/board/can-20260928/README.md)。该结果只证明
Linux 驱动下的板级物理链路，不代表 UP1/UP2 已完成 CAN 直驱或资源移交。

随后已在 Linux 解绑 CAN1/CAN3 的窗口内，由 UP1 直接控制 `0x2ab10000`、UP2
直接控制 `0x2ab30000`，连续三轮完成每轮 1,000 次经典 CAN 请求/应答；双方每轮
TX/RX 均为 1000/1000，控制器 TXERR/RXERR 均为 0。每轮结束均停止临时实例、重绑
Linux CAN，`micad` PID 和重启计数不变。见
[UP1/UP2 CAN 寄存器直驱记录](tests/board/can-direct-20260928/README.md)。该历史固件为
轮询模式，并依赖 Linux 在解绑前一次性准备 CAN pinctrl/clock/reset；CAN FD/BRS、IRQ、
FD2/FD4 及由 UP 自主初始化 CRU/pinctrl/reset 尚未完成，因此不能宣称 CAN 最终移交。
2026-10-08 使用相同测试固件再通过一轮 1,000 次请求/应答；执行器增加 CPU4/5
PSCI OFF 确认后才允许 Linux 重新绑定，累计四轮均通过。

M7.0 以已完成的 [M6 双 UniProton 基线](../stage06-multi-uniproton/README.md)为起点，保持 UP1=CPU4、UP2=CPU5 及原有内存、SGI、OpenAMP 分配。本阶段的目标是将评估板全部接口明确归属 openEuler、UP1 或 UP2，实现指定工业外设的 UniProton 物理直驱，并逐项取得可复核的实机测试证据。详细表和退出条件见 [M7.0 全资源分配与测试目标](docs/m7.0-resource-allocation-and-tests.md)。

本阶段不增加第三个 UniProton，不实现 2oo3、主备或表决。M6 的 `COMPLETE` 只说明双实例计算/通信资源隔离完成；不能据此宣称 CAN、UART、ADC、GMAC 已由 UniProton 驱动。当前资源分配是目标，不是已生效的设备树或驱动清单；实际运行映射见 [M7.0 实机资源台账](docs/m7.0-live-resource-ledger.md)。

主要候选分配：UP1 独占 CAN FD1/2、RS-485 #1、RS-232 #1 和整个 SARADC；UP2 独占 CAN FD3/4、RS-485 #2、RS-232 #2，并以软件可行性验证为门槛直驱 ETH2。openEuler 保留 ETH1 主有线管理、ETH3 USB 百兆备用/测试对端、DI/DO、I2C1 及启动/存储/维护/显示等系统资源。ETH2 允许启动阶段一次性初始化 PHY reset，但 UP2 启动后必须独立控制 GMAC1、MDIO、PHY 和运行时链路恢复；做不到则 ETH2 不移交。

正式运行时 UART4/8 分别作为 UP1/UP2 工控 RS-232，不占作常驻调试口。两 UP 各用独立保留内存日志环记录早期启动和异常，openEuler 按稳定实例身份收集到 `/userdata`；内存环和 Linux 读取/轮转的首切片已验证，详情见 [实机记录](tests/board/m7-observability-bringup-20260928.md)。独立 RPMsg 诊断端点、心跳告警与异常快照仍待实现。开发期可以临时将 UART4/8 切到物理调试用途，但会占用相应 RS-232 工控口。M7 新固件的打印路径已脱离 Linux UART0；其余条件、板卡依赖和测试标准以详细文档为准。

可复建材料：在已有 M6 UniProton 源码及交叉工具链的构建容器内，运行 `build/prepare_m7_uniproton.sh` 将 M6 源码复制到独立的 `UniProton-m7`，应用 `source/patches/uniproton/` 并覆盖 `source/overlay/uniproton/`；再运行 `build/build_m7_observability.sh` 生成 CPU4/CPU5 两份固件。准备脚本遇到已有目标目录会拒绝覆盖。Linux 读取程序及 systemd 单元见 `source/host/`；当前板卡已安装但未启用开机自启。`firmware/` 中最终重编的两份 ELF 均已通过单实例启动、日志、RPMsg 回显和停止测试，见 [最终 ELF 实机记录](tests/board/m7-final-elf-single-instance-20260928.md)。原 M6 固件、配置与 Linux 设备树未覆盖。

双实例连续停止的 `micad SIGABRT` 已定位并修复：RPC 日志原先共用全局 `FILE *`，第二个实例重复关闭已释放句柄。M7 增加共享日志引用计数、最后使用者关闭和失败清理，最终 PIE 构建已通过两种停止顺序各 20 轮、交替启动、双路回显、单边启停、CPU OFF 和 RPC 日志 fd 无泄漏回归。板卡服务通过独立路径/drop-in 使用修复版，原 `/usr/bin/micad`、M6 固件及配置保留。见 [修复与回归记录](tests/board/m7-rpc-log-lifecycle-fix-20260928.md)、[MCS 补丁](source/patches/mcs/0003-rpc-shared-log-lifecycle.patch) 和 [复建/回退说明](build/README.md)。完整 Yocto 镜像尚未重打，外设直驱仍未移交，M7.0 仍未验收。
