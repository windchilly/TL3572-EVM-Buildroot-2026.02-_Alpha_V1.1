# TL3572 / RK3572：openEuler + MICA + UniProton

本仓库保存评估板资料、Stage01–Stage07 的源码/配置、正式阶段记录，以及换机恢复入口。
2026-10-23 当前[P3h完整PDO堆预算/首错修复](stages/stage07-peripheral-partition/tests/powerlink-nmt-p3h-20261023/README.md)：
P3g失败后获新授权重启一次，Linux ETH2/3已恢复；UP2显式NMT候选堆1MiB/defaultOFF，完整通道保留、首个PDO错误不再被覆盖。
受限宿主堆100轮/175Python/两全新软件与累计树11产物一致，静态镜像/页表/栈预算通过；新候选尚未上板，硬件复测需新窗口和授权。
2026-10-23 当前[P3g单次NMT实板失败/保留现场](stages/stage07-peripheral-partition/tests/powerlink-nmt-p3g-hw-20261023/README.md)：
获准单次reset后在ResetCommunication故障，尚未NotActive/SwitchOff；真实512KiB共用堆剩148920B，小于TX PDO映射所需162560B。
已用交叉编译核实布局；独立CurrentEL检查器修正后169Python通过，不是实板通过。先保留资源，后另获准重启恢复；原失败结果保持。
下列各“本轮”描述是历史检查点，当前状态以上述故障记录为准；正式固件仍未改变。
2026-10-23 最新[P3g独立板端runner/停核快照准备](stages/stage07-peripheral-partition/tests/powerlink-nmt-p3g-runner-20261023/README.md)：
固定同一候选，补独立NMT授权/单次窗口/严格命令及收尾门槛，native与AArch64的23项ABI布局一致、168Python及旧原生回归通过。
先停核证明再rm/归还Linux，未知状态保留资源不重试；本轮未连接或部署板卡，已另询问隔离NMT reset许可，非硬件验收。
2026-10-23 最新[P3g有界NMT reset/关断软件准备](stages/stage07-peripheral-partition/tests/powerlink-nmt-p3g-20261023/README.md)：
修复reset新增PDO分配失败无限等待/循环TX表NULL访问；100次真实栈reset→NotActive→SwitchOff、25+4原生/144Python及双根11产物一致。
默认关闭、累计旧功能保留，最终TTY关键栈预算不增长；本轮未访问/部署板卡，物理reset/MN/CN/实时性尚未验收。
2026-10-23 最新[P3f栈修复与GsOff实板复测](stages/stage07-peripheral-partition/tests/powerlink-mn-p3f-fixed-20261023/README.md)：
获准精确清理后，状态路径快照/回复移至受保护BSS，输入帧1712→320B；最终调用链2944B+1KiB预留通过。
真实完整栈128次GsOff处理/停止/退出及Linux归还通过，136Python/29+4原生/双新树runtime一致；未重启/reset/start/发帧，正式固件不变。
2026-10-23 最新[P3f硬件窗口故障记录](stages/stage07-peripheral-partition/tests/powerlink-mn-p3f-hw-20261023/README.md)：
获准后首次只读PLK状态查询超时，未提交MN诊断；发现查询/日志链静态栈至少4336B超过线程4096B。
异常后CPU4/5独立确认为OFF，临时管理表/ETH2解绑/hold保留；本轮未清理、修复、重试或重启，等待新确认。
2026-10-23 最新[P3f MN完整栈GsOff生命周期软件检查点](stages/stage07-peripheral-partition/tests/powerlink-mn-p3f-20261023/README.md)：
同一UP2 owner累计接入初始化/准备/128次处理/停止/退出，100轮真实栈原生、29+3场景及129Python通过，两新树runtime一致。
默认关闭/无reset或start/未上板；真实MN启动、CN互操作及实时验收仍未完成。
2026-10-23 最新[P3e EDRV隔离物理收发](stages/stage07-peripheral-partition/tests/powerlink-edrv-p3e-20261023/README.md)：
UP2直驱ETH2，100M half下64B/1514B各32组请求应答；RX/TX完成/FCS各64、硬件错误0、安全停止及Linux归还通过。
122Python/新增17+3原生场景及累计回归、双新树runtime一致；无MN/CAN/UART发送、重启或正式固件替换，MN/CN互操作尚未验收。
2026-10-23 [P3d半双工实测与修复](stages/stage07-peripheral-partition/tests/powerlink-eth-p3d-hw-20261023/README.md)：
修正真实ETH BSP错误ISA约束导致的CASAL异常，最终LSE零；UP2 PHY/MAC100-half及ETH3匹配三轮、安全归还通过。
115Python/原生回归/双新树复编通过，无测试帧/MN启动/整板重启/正式固件替换；仍未验收EDRV物理收发与CN互操作。
2026-10-10 最新[P3d无帧ETH2诊断软件准备](stages/stage07-peripheral-partition/tests/powerlink-eth-p3d-20261010/README.md)：
累计UP2保留timer并补COLD显式PHY/MAC100-half检查，禁止DMA/帧/MN启动；8+3原生、104Python及双新树复编通过。
未部署或改变板端ETH2，半双工实机待单独确认；正式固件/M6/DT不变，CAN/UART不发送仍有效。
2026-10-10 最新[P3c定时器检查点](stages/stage07-peripheral-partition/tests/powerlink-timer-p3c-20261010/README.md)：
UP2 CNTP/PPI30权限、72次真实IRQ/任务回调及安全退出通过；修正GICv2非安全分组视图误判。
99项Python/原生回归、两个全新累计树runtime一致；样本最大IRQ迟到29.292us、任务迟到89.75us，非最坏时延保证。
仅临时UP2诊断，原两UP已Offline；无外设帧/重启/正式固件替换。半双工、MN运行及CN互操作仍未验收。
2026-10-10 最新软件增量：UP2/ETH2 POWERLINK MN推进至P3b休眠owner/邮箱/诊断与完整累计候选ELF链接；
12组原生任务测试、92项Python及双目录11产物一致；[P3b证据与换机入口](stages/stage07-peripheral-partition/tests/powerlink-mn-p3b-20261010/README.md)。
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
