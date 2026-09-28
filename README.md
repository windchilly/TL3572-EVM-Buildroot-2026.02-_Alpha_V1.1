# TL3572 / RK3572：openEuler + MICA + UniProton

本仓库保存评估板资料、Stage01–Stage07 的源码/配置、正式阶段记录，以及换机恢复入口。
M6 双 UniProton 已完成；M7 当前完成日志/RPC 软件，工业外设直驱尚未实现、未验收。

## 从哪里开始

| 目的 | 入口 |
|---|---|
| 换机恢复各阶段完整源码 | [全阶段恢复与构建](repro-inputs/all-stages/README.md) |
| 查看阶段功能和交付材料 | [阶段索引](stages/README.md) |
| 查看完整移植路线 | [总移植路径](TL3572_openEuler_MICA_UniProton_2oo3_完整移植路径.md) |
| 继续开发、了解当前状态 | [交接记录](memory.md) |
| 查看构建验证证据 | [全阶段验证](repro-inputs/all-stages/tests/verification.md)、[M6/M7 干净构建](repro-inputs/rk3572/tests/clean-rebuild.md) |
| 查看目录归属、清理和维护规则 | [工作区目录规范](docs/operations/workspace-layout.md) |

## 分类

- `1-产品规格书/` 至 `7-关于Tronlong/`：厂商资料、硬件资料、厂商源码和工具链；保留原厂路径。
- `stages/`：按阶段保存设计、正式源码修改、构建/测试脚本、参考固件和历史证据。
- `repro-inputs/`：共享源码、完整阶段输入、固定版本清单与空目录复建脚本；不存旧编译缓存。
- `docs/operations/`：本地/服务器目录映射、维护规范和本次整理记录。
- `scripts/maintenance/`：默认只预览、精确限定对象的维护脚本。
- `.local-only/`：只留本机的原厂整体 SDK、嵌套 Git 元数据备份和维护操作清单，不上传 GitHub。

正式 `release-*` 包、源码归档、SHA256 清单及其相对路径不因本次整理而改变。
构建容器仍使用固定 Docker 摘要；参见复现入口，不需要原开发容器中的旧 tmp/sstate。
