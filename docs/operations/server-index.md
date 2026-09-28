# openEuler 构建目录入口

本文件同时放置在开发容器 `/home/openeuler/build/README.md`。

| 用途 | 容器路径 |
|---|---|
| TL3572 活动工程 | `/home/openeuler/build/projects/tl3572/current/` |
| TL3572 独立复现验证 | `/home/openeuler/build/projects/tl3572/reproduction/20260928/` |
| TL3572 最终源码导出归档 | `/home/openeuler/build/projects/tl3572/exports/20260928/` |
| 成功验证与导出日志 | `/home/openeuler/build/projects/tl3572/evidence/20260928/` |
| 失败运行日志与输入清单 | `/home/openeuler/build/projects/tl3572/archive/failed-runs/20260928/` |
| 目录整理操作记录 | `/home/openeuler/build/projects/tl3572/maintenance/20260928/` |
| 树莓派活动工程 | `/home/openeuler/build/projects/rpi4/current/` |
| 树莓派 UEFI / 发布包 | `/home/openeuler/build/projects/rpi4/` |
| 共用源码、工具链、下载和缓存 | `/home/openeuler/build/projects/shared/` |

原 `/home/openeuler/build/tl3572-2oo3/` 主工程没有移动，构建绝对路径不变。
旧的成功导出/验证路径保留相对链接；新任务从分类入口进入。
独立 RK3588 工程、SDK、工作树、报告及其镜像已按用户确认永久删除；树莓派保留。
不完整导出、重复展开树及两次失败的复现工作区已删除，日志和来源清单已归档。

Stage01–Stage07 的换机入口仍为源码仓库 `repro-inputs/all-stages/README.md`，
固定复现提交 `2e6074a506111b301ffc146650ef15966da47bf5` 和 Docker 摘要，不依赖此目录的旧缓存。
需要正常复现时执行仓库维护良好的入口，不使用 `tools/20260928/` 中的早期辅助副本。
禁止批量清理共享目录或执行全局 Docker prune。
