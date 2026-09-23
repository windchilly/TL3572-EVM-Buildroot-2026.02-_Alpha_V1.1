# Stage 01–05 容器输入归档

本目录于 2026-09-23 从 `dev_openeuler` 容器的
`/home/openeuler/build/tl3572-2oo3/` 提取仍然存在的 Stage 01–05 构建输入。
`SHA256SUMS` 覆盖本次提取的 43 个文件；新增的本说明不在该清单内。

## 上游源码基线

`upstream/` 的七个压缩包由容器中对应 Git 工作树的固定 `HEAD` 执行
`git archive --format=tar HEAD | gzip -n -1` 生成，不包含 `.git`、未提交改动、
构建输出或下载缓存。解压到工作区的 `src/<仓库名>/` 即可恢复这些提交的源码内容。
各仓库原有许可证文件保留在压缩包中。

| 压缩包 | 提交 |
|---|---|
| `yocto-meta-openeuler.tar.gz` | `3aa6999c9ab78569bc2209a9dbb185e2f7e4301c` |
| `yocto-poky.tar.gz` | `4bf0e3ea7a5cd4577ae43c510870f235a39eedc0` |
| `yocto-meta-openembedded.tar.gz` | `a82d92c8a6525da01524bf8f4a60bf6b35dcbb3d` |
| `mcs.tar.gz` | `5cb49156276be04d54a77a630b8600dcc122fdba` |
| `UniProton.tar.gz` | `1d102888822449b8205894db4f483abc71c0d05b` |
| `OpenAMP.tar.gz` | `5fbe563479c2c137a442659e87f603dd323a03c3` |
| `libmetal.tar.gz` | `69e96d9620652df428ec7f4faca92f70cce111d3` |

这些提交与 `stages/stage01-baseline/TL3572-stage01-baseline-manifest.md`
一致。UniProton 的 Stage 05 修改须在该基线上应用
`stages/stage05-uniproton/source/overlay/uniproton-rk3572-m5-source-overlay.tar.gz`；
容器中后续 Stage 06 的工作树改动没有混入基线压缩包。

## 阶段文件

- `stage02/meta-tl3572/` 是容器中保留的早期完整 Yocto 层；
  `stage02/build-conf/` 和 `stage02/compile.yaml` 是该阶段的配置快照。
- `config/` 保存容器工作区根目录的 Stage 03 `compile.yaml`、
  `compile-stage3.yaml` 和 `local-stage3.conf`。
- `scripts/` 保存当时的 Stage 02–04 构建、配置、打包和验证脚本。
  它们使用原构建机的绝对路径，其中有清理临时构建目录的脚本；移植环境前先阅读脚本。
- `stage03/manifests/` 保存容器内的基线清单和 M2 修改前镜像配方。
- `stage04/` 保存独立模块源码及预留 CPU 调整前的内核配置。
- `stage05/tl3572-up0.conf` 是容器中的单实例配置；Stage 05 的正式补丁、
  源码覆盖包、配方、固件和测试记录仍以 `stages/stage05-uniproton/` 为准。

这批文件补齐了容器中仍可取得的早期层和本地源码输入。容器中的
`meta-tl3572-stage3` 已连续演进到 Stage 06；未找到 Stage 03/04/05
各自完整且未修改的独立层快照。因此，本归档不能证明每个历史阶段都能按当时状态
逐字节独立重建。当前最终层在 `repro-inputs/meta-tl3572-stage3/`。

构建仍需 Stage 01 清单指定的 openEuler 容器环境及其中的 GCC 12.3/Native SDK；
Arm GNU 14.3 工具链见 `4-软件资料/Linux/Tools/`。下载缓存和 sstate 未上传，
首次构建可能需要联网。Stage 02–04 的大型已生成 rootfs/update 镜像仍按
`GITHUB_UPLOAD_SCOPE.md` 排除。尚未从全新 GitHub 克隆执行 Stage 01–05 的完整复建。
