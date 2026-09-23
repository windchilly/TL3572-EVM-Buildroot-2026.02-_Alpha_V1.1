# TL3572 阶段资料索引

阶段目录统一使用 `stageNN-purpose` 命名。大型镜像发布包使用 `release-*`，过程记录
使用 `worklog-*`，不再参与当前构建但仍有追溯价值的内容放入 `archive/`。

| 目录 | 内容 | 状态 |
|---|---|---|
| `stage01-baseline/` | 厂商基线与初始清单 | 完成 |
| `stage02-rootfs/` | openEuler rootfs 与 mcsctl | 完成 |
| `stage03-yocto-bsp/` | Yocto BSP、rootfs 和 update.img | 完成 |
| `stage04-mica-mcs/` | Linux MICA/MCS 适配与正式镜像 | 完成 |
| `stage05-uniproton/` | 单 UniProton 源码、固件、构建和验收 | 完成（延期项见报告） |
| `stage06-multi-uniproton/` | 双 UniProton；CPU4/CPU5 独立 SGI、内存与 RPMsg | 完成（功能与构建范围） |

规则：

- `release-*` 内部结构及已有 SHA256 清单保持不变；
- 当前可复现材料放在阶段目录的正式分类中；
- `archive/` 只用于历史调试和中间版本，不作为部署输入；
- 新阶段延续 `stage06-*`、`stage07-*` 格式，不再在工作区根目录新建散乱目录。
