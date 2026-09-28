# 2026-09-28 本地完整目录重构

本次是原厂资料的实际搬迁和用途分类，不是只加索引或清缓存。
此前服务器 RK3588 删除和约 125.33 GiB 释放是另一次已完成操作，
见 [初次整理记录](cleanup-20260928.md)，不作为本次新释放空间重复计算。

## 实际分类

| 新位置 | 归入的原始内容 |
|---|---|
| `hardware/specifications/` | 原产品规格，分核心板、底板、本板配套附件 |
| `hardware/core-board/`、`carrier-board/` | 引脚、CAD、原理图、PCB、BOM、机械/位号图 |
| `hardware/datasheets/`、`design-guides/` | 元件手册、硬件说明、底板设计指南 |
| `software/sources/` | 完整 Kernel / U-Boot / Buildroot 原厂源包 |
| `software/toolchains/` | 固定 Arm GNU 14.3 工具链 |
| `software/examples/` | CAN、串口、GPIO、通信、音频、GUI 等原厂示例 |
| `software/firmware/` | 厂商 boot、loader、U-Boot 和本机 rootfs/update 镜像 |
| `docs/manuals/`、`reference/rockchip/` | 原使用手册与全部技术参考/补丁/SBOM |
| `docs/project/`、`vendor-notes/`、`operations/` | 路线图、开箱/更新/软件特性、上传范围与维护记录 |
| `.local-only/tools/windows/` | 按刷机、驱动、工控、通信、诊断分类的 Windows 板级工具 |

原 `1-产品规格书` 至 `7-关于Tronlong` 七个顶层目录已全部撤除，没有保留空壳、
Windows junction 或旧目录别名。根目录只保留项目入口 `README.md`、交接 `memory.md`
及 Git 配置文件；用途目录为 `hardware / software / docs / stages / repro-inputs / scripts`，
另有隐藏的 `.git / .local-only`。

`stages/` 与 `repro-inputs/` 已按阶段/构建用途划分，保留其内部正式文件位置，
不把阶段固件与源码包混进厂商目录。CAD 配套文件、技术文档内部子目录、原包版本名
和包内结构原样保留。原厂完整 SDK/dl/sysroot 继续留在 `.local-only/vendor-sdk/`。

## 清除的无关材料

以下五个实际文件已移入 Windows 回收站，可恢复；没有清空回收站。
总计 **190,111,270 B（约 181.30 MiB）**，不能据此声称磁盘已释放同等空间。

- Tronlong 售后服务说明。
- Tronlong 产品返修单。
- 跨产品嵌入式板卡快速选型/宣传手册。
- 嵌入式交流群推广文件。
- 与本项目构建无关的 `VMwareWorkstatiozcj.exe`。

与本板有关的配件规格、厂商测试手册、全部硬件设计文件、源包、工具链和唯一固件
均保留。清除会在新提交中体现；不会抹掉之前的 Git 历史。

## 路径与内容验证

执行工具为 [restructure-local.ps1](../../scripts/maintenance/restructure-local.ps1)，
默认预览；输入为 [精确搬迁/回收方案](local-reorganization-plan.json)。
`-Apply` 先检查真实绝对路径、符号链接、目标冲突和全部文件哈希；
只移除已空的旧目录，拒绝重复覆盖已存在的实际操作报告。

37 个明确搬迁目标共 **774 个文件、4,891,488,590 B**。
搬迁后逐文件核验 **774/774 SHA-256 一致**，包含未上传的原厂镜像和板级工具。
实际逐文件清单在忽略的 `.local-only/maintenance/local-reorganization-20260928.json`。
随后对总路线、上传范围和 SDK 说明等文档更新路径；不把这些有意文档修改称为字节不变。

根 README、分类 README、M7 硬件引用和复现说明已改为新路径。
唯一直接读取旧厂商顶层路径的构建入口是 `repro-inputs/rk3572/scripts/prepare.sh`：
优先读取 `software/toolchains/`，保留历史路径回退，两处必须满足同一固定 SHA-256。
旧固定复现提交 `2e6074a506111b301ffc146650ef15966da47bf5` 原样保留，
新分类不重写历史提交、不重生成大源码包、不替换工具链版本。

历史交接、原始日志与之前清理脚本保留当时路径；需要查找时按搬迁方案映射，
不改写历史测试证据，也不再次执行已完成的旧清理脚本。

## 整理后的实测

- 本地结构检查 **6/6 通过**：七个旧目录消失、原跟踪文件按映射保留、
  全阶段输入 **24/24 SHA-256**、固定工具链哈希、活动文档链接以及未编辑搬迁文件的哈希。
- Git 确认 **749 项重命名**，其中 746 项内容完全一致，3 项随路径迁移更新文档引用。
  受跟踪文件仅删除上面的四份售后/返修/宣传资料；VMware 辅助程序原本被忽略。
- 固定摘要容器 `tl3572-local-structure-stage02-20260928`，`network=none`，
  工作区 `projects/tl3572/reproduction/20260928/local-structure-smoke/work/` 从空目录开始。
  `/repo` 只暴露新 `software/toolchains/` 位置，没有旧 `4-软件资料` 目录，
  因而不能依靠 prepare 的历史路径回退蒙混通过。
- 验证入口使用此前已经校验的源包，只读挂载在 `/retained`；测试入口的
  `repro-inputs/stages` 指向这些只读输入，工具链以只读硬链接暴露在新路径。
  不挂载旧 build/tmp/sstate，未修改保留源码克隆；不是另一次全新 GitHub 下载测试。
- 当前 prepare、Stage02 独立恢复及禁网 fetch 完整通过：**215/215，零复用**。
  Linux 归档单测 **4/4**、M7 日志单测 **5/5** 通过；测试容器已停止，工作区及日志保留。
- PowerShell / Bash 语法与 Git LFS fsck 通过。没有登录、刷写、重启板卡，
  没有新编译整镜像或重新验收 M7 外设驱动。

原始日志见 [logs/local-reorganization-20260928/](logs/local-reorganization-20260928/)，
有独立 SHA256SUMS。用户明确确认本次完整目录重构同步到 GitHub；
以普通新提交记录，不改写原历史、固定复现提交或 LFS 源码归档内容。
