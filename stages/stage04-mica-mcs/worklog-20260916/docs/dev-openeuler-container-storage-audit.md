# dev_openeuler 构建容器空间审计（2026-09-17）

## 1. 范围与结论

本次检查及清理仅作用于 `10.100.60.226:2005` 的 `dev_openeuler` 构建容器，不检查、不处理宿主机。
清理前未发现运行中的 BitBake、oebuild、make、gcc 等构建进程。用户确认后，已按精确路径删除第 2、3 节列出的五个目标。

- 清理前文件系统：约 1.7 TiB，已用约 1.2 TiB，可用约 435 GiB，使用率 73%；
- 清理后文件系统：已用约 946 GiB，可用约 628 GiB，使用率 61%；
- `/home/openeuler/build` 从约 358.9 GiB 降至约 166.0 GiB；
- 实测释放约 192.9 GiB（删除目标清理前统计合计约 195.8 GiB，差异来自目录统计和底层块计量）；
- 当前 TL3572 构建 `tmp` 另占约 21.5 GiB，可删除但会增加后续重建时间，暂列可选项。

## 2. 第一批：已删除

| 路径 | 清理前实际占用 | 结果 |
|---|---:|---|
| `/home/openeuler/build/tl3572-2oo3/logs/uboot-tools-build.log` | 112.18 GiB | 已删除；异常失控日志，U-Boot Kconfig 在 EOF 后反复输出 `Define AVB buffer address` / `Error in reading or end of file` |
| `/home/openeuler/build/tl3572-2oo3/build/build-rootfs/tmp` | 21.89 GiB | 已删除；阶段 2 Yocto 临时构建树，可重建 |
| `/home/openeuler/build/tl3572-2oo3/build/build-tl3572/tmp-mixed-hosttools-20260916` | 5.34 GiB | 已删除；阶段 4 排错期间产生的临时 TMPDIR |

合计约 139.4 GiB。删除异常日志前如需留证，只需保留少量文件头尾和本审计中的根因摘要，无需保留 112 GiB 原文件。

## 3. 第二批：已删除旧参考项目临时目录

| 路径 | 清理前实际占用 | 结果与影响 |
|---|---:|---|
| `/home/openeuler/build/build/build-rk3588-openeuler-ok3588-toolchain-20260820/tmp` | 29.93 GiB | 已删除；`conf`、`output`、源码和交付件保留，只有重编该旧目标时才会重新生成 |
| `/home/openeuler/build/build-rpi4-mica-uniproton/tmp` | 26.49 GiB | 已删除；`conf`、`output` 和已有 artifacts 保留，只有重编该旧目标时才会重新生成 |

合计约 56.4 GiB。上述两个目录最后活动时间分别为 2026-08-20 和 2026-08-17，当前无相关构建进程。

## 4. 可选进一步清理

| 内容 | 可释放空间 | 建议 |
|---|---:|---|
| `/home/openeuler/build/tl3572-2oo3/build/build-tl3572/tmp` | 21.49 GiB | 当前正式 TL3572 Yocto TMPDIR；可以重建，但阶段 5 可能继续使用，优先保留以缩短构建时间 |
| 阶段 2 `build-rootfs/output` 历史版本，仅保留 `20260915082322` | 约 4.43 GiB | 最新版本已保留，旧时间戳输出可删 |
| 阶段 3/4 `build-tl3572/output` 历史版本，仅保留 `20260916104226` | 约 0.94 GiB | 最新正式产物已保留，旧时间戳输出可删 |
| `tl3572-2oo3/images/stage2*` 三套阶段 2 镜像 | 约 1.01 GiB | Windows 已有阶段交付副本时可删；否则保留一套最终修正版 |
| `/home/openeuler/build/r1-media` | 约 9.22 GiB | 含 RK3588 USB/p1/p2 镜像，可能用于阶段 5 参考；确认不再需要后才删 |

## 5. 不应删除

- `/home/openeuler/build/vendor_sdk`（约 79.4 GiB）：几乎全部是 RK3588 仓库的 `.git/objects`；
  `/home/openeuler/build/rk3588_worktrees/ctb8815-r1/.git` 明确指向该仓库的
  `.git/worktrees/ctb8815-r1`。直接删除会破坏约 22.1 GiB 的 RK3588 参考工作树；
- `/home/openeuler/build/rk3588_worktrees/ctb8815-r1`：阶段 5 单 UniProton 移植的重要参考；
- `/home/openeuler/build/tl3572-2oo3/src`、`meta-tl3572-stage3`、内核补丁、配置、
  `kernel-src-pristine`、`kernel-src-vendor.tar.gz`：属于源码、可重复构建输入或溯源材料；
- `/home/openeuler/build/sstate-cache`、`downloads` 和 `tl3572-2oo3/sstate-stage3`：总量不大，
  能显著缩短后续构建，不建议为少量空间清理；
- Windows 已交付的阶段 4 完整镜像、SHA256 清单和实机验证记录。

## 6. 执行后保留项复核

- 当前 TL3572 正式 `tmp`：约 22 GiB，已保留；
- 共享 `sstate-cache`：约 3.6 GiB，已保留；
- `downloads`：约 23 MiB，已保留；
- TL3572 `src`：约 3.5 GiB，已保留；
- `meta-tl3572-stage3`：约 310 MiB，已保留；
- TL3572 正式 `output`：约 1.3 GiB，已保留；
- 当前 TL3572 正式 `tmp`、历史 output 和 `r1-media` 仍按第 4 节列为后续可选项。
