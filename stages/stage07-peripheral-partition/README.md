# Stage 07 / M7.0：全资源划分与外设直驱

当前状态：`IN PROGRESS / 全资源目标已规划 / 日志首切片实机验证 / Linux CAN 物理基线实机验证 / 外设尚未移交 / M7.0 未验收`。

2026-09-28 已补齐 [GitHub 换机输入与构建入口](../../repro-inputs/rk3572/README.md)，
在空目录、固定基础容器中断网重建 M6 完整镜像、M6/M7 双固件、M7 MCS 软件包及
独立修复版 micad，均通过；四份固件和独立 micad 与实机版本逐字节一致。
见 [独立复现记录](../../repro-inputs/rk3572/tests/clean-rebuild.md)。这是现有软件切片的
可复建性验证，不是完整 M7 镜像或工业外设直驱验收，新产物未部署到板卡。

2026-09-28 已将 CAN FD1（Linux `can1`，M7.0 目标 UP1）与 CAN FD3
（Linux `can3`，M7.0 目标 UP2）组成物理总线完成经典 CAN 基线测试：每接口累计
收发各 10,640 帧、三轮 stop/start 恢复，错误/丢包/bus-off 均为 0。当前
`rk3576_can` 驱动拒绝启用 FD/BRS，因此 CAN FD 数据相位仍未验证。原始证据和边界见
[CAN FD1 ↔ CAN FD3 物理基线记录](tests/board/can-20260928/README.md)。该结果只证明
Linux 驱动下的板级物理链路，不代表 UP1/UP2 已完成 CAN 直驱或资源移交。

M7.0 以已完成的 [M6 双 UniProton 基线](../stage06-multi-uniproton/README.md)为起点，保持 UP1=CPU4、UP2=CPU5 及原有内存、SGI、OpenAMP 分配。本阶段的目标是将评估板全部接口明确归属 openEuler、UP1 或 UP2，实现指定工业外设的 UniProton 物理直驱，并逐项取得可复核的实机测试证据。详细表和退出条件见 [M7.0 全资源分配与测试目标](docs/m7.0-resource-allocation-and-tests.md)。

本阶段不增加第三个 UniProton，不实现 2oo3、主备或表决。M6 的 `COMPLETE` 只说明双实例计算/通信资源隔离完成；不能据此宣称 CAN、UART、ADC、GMAC 已由 UniProton 驱动。当前资源分配是目标，不是已生效的设备树或驱动清单；实际运行映射见 [M7.0 实机资源台账](docs/m7.0-live-resource-ledger.md)。

主要候选分配：UP1 独占 CAN FD1/2、RS-485 #1、RS-232 #1 和整个 SARADC；UP2 独占 CAN FD3/4、RS-485 #2、RS-232 #2，并以软件可行性验证为门槛直驱 ETH2。openEuler 保留 ETH1 主有线管理、ETH3 USB 百兆备用、DI/DO、I2C1 及启动/存储/维护/显示等系统资源。ETH2 允许启动阶段一次性初始化 PHY reset，但 UP2 启动后必须独立控制 GMAC1、MDIO、PHY 和运行时链路恢复；做不到则 ETH2 不移交。

正式运行时 UART4/8 分别作为 UP1/UP2 工控 RS-232，不占作常驻调试口。两 UP 各用独立保留内存日志环记录早期启动和异常，openEuler 按稳定实例身份收集到 `/userdata`；内存环和 Linux 读取/轮转的首切片已验证，详情见 [实机记录](tests/board/m7-observability-bringup-20260928.md)。独立 RPMsg 诊断端点、心跳告警与异常快照仍待实现。开发期可以临时将 UART4/8 切到物理调试用途，但会占用相应 RS-232 工控口。M7 新固件的打印路径已脱离 Linux UART0；其余条件、板卡依赖和测试标准以详细文档为准。

可复建材料：在已有 M6 UniProton 源码及交叉工具链的构建容器内，运行 `build/prepare_m7_uniproton.sh` 将 M6 源码复制到独立的 `UniProton-m7`，应用 `source/patches/uniproton/` 并覆盖 `source/overlay/uniproton/`；再运行 `build/build_m7_observability.sh` 生成 CPU4/CPU5 两份固件。准备脚本遇到已有目标目录会拒绝覆盖。Linux 读取程序及 systemd 单元见 `source/host/`；当前板卡已安装但未启用开机自启。`firmware/` 中最终重编的两份 ELF 均已通过单实例启动、日志、RPMsg 回显和停止测试，见 [最终 ELF 实机记录](tests/board/m7-final-elf-single-instance-20260928.md)。原 M6 固件、配置与 Linux 设备树未覆盖。

双实例连续停止的 `micad SIGABRT` 已定位并修复：RPC 日志原先共用全局 `FILE *`，第二个实例重复关闭已释放句柄。M7 增加共享日志引用计数、最后使用者关闭和失败清理，最终 PIE 构建已通过两种停止顺序各 20 轮、交替启动、双路回显、单边启停、CPU OFF 和 RPC 日志 fd 无泄漏回归。板卡服务通过独立路径/drop-in 使用修复版，原 `/usr/bin/micad`、M6 固件及配置保留。见 [修复与回归记录](tests/board/m7-rpc-log-lifecycle-fix-20260928.md)、[MCS 补丁](source/patches/mcs/0003-rpc-shared-log-lifecycle.patch) 和 [复建/回退说明](build/README.md)。完整 Yocto 镜像尚未重打，外设直驱仍未移交，M7.0 仍未验收。
