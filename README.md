# TL3572 / RK3572：openEuler + MICA + UniProton

本仓库保存评估板资料、Stage01–Stage07 的源码/配置、正式阶段记录，以及换机恢复入口。
2026-10-10 最新软件增量：UP2/ETH2 POWERLINK MN 的 P0 核心、P1 EDRV、P2 target/cache/CNTP
均已完成软件编译/原生检查与独立复编；[P2 证据与换机入口](stages/stage07-peripheral-partition/tests/powerlink-mn-p2-20261010/README.md)。
尚无 MN 运行入口、半双工/定时精度或 CN 互操作验收，正式累计 ELF 保持实测版本。
M6 双 UniProton 已完成；M7 已完成日志/RPC 软件及 CAN1↔CAN3 的经典 CAN、
CAN FD/BRS、UART4↔UART8 RS-232 及 UART1↔UART2 RS-485 自主字段初始化/IRQ 直驱切片，
完整外设移交与 M7.0 尚未验收。板上 UART3 对应 SoC UART8；CAN FD2/FD4 本轮跳过、未验证。
2026-10-09 已将上述驱动、日志及诊断合并为UP1/UP2两份统一固件，运行时选参数、默认不发送；
构建/复编及无硬件检查通过，软件合并证据见
[合并记录](stages/stage07-peripheral-partition/tests/board/integrated-20261009/README.md)。
随后被动上板发现UP1页表需要36KiB、仅预留32KiB，MMU初始化失败被忽略并触发RPMsg对齐异常。
现已仅对统一目标扩至64KiB、增加启动检查和实际PTE验收；修复两ELF通过四轮被动双实例回归。
用户已改变接线并要求不发送，物理测试仍暂停；不是组合工控收发或M7.0验收。
见[修复与回归记录](stages/stage07-peripheral-partition/tests/board/integrated-mmu-fix-20261009/README.md)，
原始[失败证据](stages/stage07-peripheral-partition/tests/board/integrated-passive-20261009/README.md)保留在固定提交。

2026-10-09 按“先解决ETH3”要求补齐专用电源使能，恢复SR9900枚举与100M全双工链路；
ETH2↔ETH3两轮Linux物理对测每方向累计4000帧通过，开机电源服务已启用，冷启动未测。
这是ETH2直驱的Linux测试对端准备，不是UP2以太网直驱通过；CAN/串口发送限制仍有效。
见[ETH3恢复记录](stages/stage07-peripheral-partition/tests/board/eth3-recovery-20261009/README.md)。

## 从哪里开始

| 目的 | 入口 |
|---|---|
| 换机恢复各阶段完整源码 | [全阶段恢复与构建](repro-inputs/all-stages/README.md) |
| 查看阶段功能和交付材料 | [阶段索引](stages/README.md) |
| 查看完整移植路线 | [总移植路径](docs/project/migration-plan.md) |
| 继续开发、了解当前状态 | [交接记录](memory.md) |
| 查看构建验证证据 | [全阶段验证](repro-inputs/all-stages/tests/verification.md)、[M6/M7 干净构建](repro-inputs/rk3572/tests/clean-rebuild.md) |
| 查看目录归属、清理和维护规则 | [工作区目录规范](docs/operations/workspace-layout.md) |
| 查板卡规格、原理图、引脚与元件手册 | [硬件索引](hardware/README.md) |
| 查厂商源码、工具链、示例和回滚固件 | [软件索引](software/README.md) |
| 查操作手册、Rockchip 参考文档和上传范围 | [文档索引](docs/README.md) |

## 分类

```text
hardware/       规格、核心板/底板设计、引脚、原理图、PCB/BOM、元件手册
software/       厂商源码包、交叉工具链、示例程序、参考固件
repro-inputs/   openEuler / UniProton 全阶段完整构建输入及空目录复现入口
stages/         Stage01–Stage07 设计、实现、测试、正式固件与历史证据
docs/           项目路线、使用手册、技术参考、厂商版本说明、运维记录
scripts/        工作区维护工具
.local-only/    本机 SDK、Windows 板级工具、元数据备份和实际操作清单（不上传）
```

原厂七个编号顶层目录已实际撤除；售后/返修和宣传资料已移入回收站。
旧路径到新路径、清理对象与哈希检查见 [本地结构重构记录](docs/operations/local-reorganization-20260928.md)。
`stages/`、`repro-inputs/` 的正式包和校验清单保持原内部结构，避免破坏阶段复现。
厂商文件的版本名和包内结构保持不变；仅按用途迁移外层位置。
旧的固定复现提交 `2e6074a` 保留原布局，当前脚本同时识别新旧工具链路径。
构建容器仍使用固定 Docker 摘要；参见复现入口，不需要原开发容器中的旧 tmp/sstate。
