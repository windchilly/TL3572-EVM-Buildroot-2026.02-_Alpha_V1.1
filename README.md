# TL3572 / RK3572：openEuler + MICA + UniProton

本仓库保存评估板资料、Stage01–Stage07 的源码/配置、正式阶段记录，以及换机恢复入口。
M6 双 UniProton 已完成；M7 当前完成日志/RPC 软件，工业外设直驱尚未实现、未验收。

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
