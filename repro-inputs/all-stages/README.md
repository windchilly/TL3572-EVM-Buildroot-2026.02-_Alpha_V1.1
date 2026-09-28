# 全阶段完整源码归档与恢复

范围为 Stage01–Stage07：每个 Stage 的正式收口版本，以及 M7 当前已经实现的
日志/RPC 软件。阶段中间的调试记录继续保留在 `stages/`；已经被历史清理掉的
M5.1/M5.2 等临时工作树无法补造为原始快照。

## 源码保存方式

共享的完整源文件只存一份，按路径和 SHA-256 固定；各阶段另有独立配置、层和
完整有效源码包。不是只存补丁，也不需要从原构建容器复制未归档的目录。

| 阶段 | 完整源码与阶段输入 | 来源说明 |
|---|---|---|
| Stage01 | 七个固定上游仓库、150 个 openEuler 包目录、厂商 6.12.69 / openEuler 5.10 内核、已有厂商 Buildroot/U-Boot 源码 | 共享归档；Stage01 本身只有基线审计，没有固件构建目标 |
| Stage02 | 早期完整 `meta-tl3572`、原始 rootfs 配置、完整 MCS | 保留的原始层与配置 |
| Stage03 | 独立 M2 层/配置、完整 MCS、共享 openEuler/厂商源码 | 从保留的 M1 配方、M5 配方和历史政策重建 M2 层；M1 原配方另保留 |
| Stage04 | 独立层/配置、完整有效 6.12.69 内核、完整 MCS、适配后的模块源文件 | 从历史层生成脚本、幸存内核工作树、正式内核配置重建 |
| Stage05 | 独立层/配置、完整有效内核、完整 UniProton/MCS、libboundscheck/lwIP/OpenAMP/libmetal 源码 | M5 正式覆盖包与配方；内核配置从正式 boot 的 IKCONFIG 核验；层其余部分重建 |
| Stage06 | 独立原始最终层/配置、完整有效内核、完整 UniProton/MCS | 当前 M6 输入；内核双 SGI、CPU4/5 预留 |
| Stage07 | 独立日志/RPC 软件层、完整 UniProton/MCS、Linux 日志读取器及测试源码 | 已实现软件；内核复用 M6，不宣称已实现外设直驱 |

`stageNN-uniproton-complete.tar.gz` 和 `stageNN-mcs-complete.tar.gz`
是可直接解压的完整源码树，不是覆盖包。`stage04/05/06-kernel-6.12.69-complete.tar.gz`
也是应用各阶段补丁后的完整内核树，包含阶段 `.config` / `localversion`，不含旧编译输出。
Stage07 尚未更改内核，明确共用 Stage06 内核包。

`stageNN-profile.tar.gz` 保存完整的阶段文本层和构建配置。
其中的相同大文件（厂商内核原始包、vendor boot、模块/固件资产、参考 ELF）通过
`STAGES.json` 的 `shared_files` 引用已有实际文件，恢复脚本会校验后补齐到层内。
Yocto 仍采用“完整原始内核 + 正式补丁”的原构建方式；额外的完整有效内核树用于审阅和独立开发。

共享源文件入口：

- `../stage01-05/upstream/`：七个固定提交的完整源码树。
- `../rk3572/openeuler-packages.tar.gz`：150 个实际 openEuler 包输入目录，含源码包、spec、补丁和许可证。
- `../rk3572/downloads.tar.gz`：必需的源下载归档/源 Git 镜像，不是 sstate。
- `historical/openeuler-kernel-5.10-complete.tar.gz`：固定提交
  `920880cbeb4a3390da6f9e95508b29abbf45140d` 的 73,335 个跟踪源文件。
- `../meta-tl3572-stage3/recipes-kernel/linux/files/`：完整原始厂商 6.12.69 内核及 boot 输入。
- 仓库 `software/sources/` 和 `software/toolchains/`：厂商 Buildroot、U-Boot、内核源包和 Arm GNU 14.3 工具链。
  下方固定复现提交使用整理前的 `4-软件资料/Linux/` 布局；当前脚本兼容两种工具链位置，哈希不变。

`SOURCE-INVENTORY.json` 和 `historical/HISTORICAL-INVENTORY.json` 使用 Git LFS，
记录归档成员和逐文件校验值；小型 `STAGES.json` 便于直接审阅阶段差异及来源。
`SHA256SUMS` 分别校验本目录及 historical 目录的归档。

本轮新增约 1.06 GiB，全仓库当前实际文件约 4.31 GiB / 4.63 GB；不是 Git/LFS 历史缓存总量。
所有完整归档已从 GitHub 独立下载，24 项校验全部一致。

## 换机恢复 / 构建

Linux x86_64 主机需安装 Docker、Git、Git LFS。固定本次完整输入、最终构建脚本和验证记录的
提交为 `2e6074a506111b301ffc146650ef15966da47bf5`；后续 main 的变化不影响此版本：

```sh
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/windchilly/TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1.git tl3572-all-stages
cd tl3572-all-stages
git checkout --detach 2e6074a506111b301ffc146650ef15966da47bf5
git lfs pull
```

Docker 仍按用户确认的固定摘要联网下载，镜像本身没有额外上传：

```text
swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f
```

例：从空目录恢复 M5。以下命令在克隆仓库根目录执行：

```sh
export REPRO_STAGE=stage05
export REPRO_CONTAINER=tl3572-stage05-repro
export REPRO_WORKSPACE=/absolute/new-directory-outside-repository
export REPRO_JOBS=8
bash repro-inputs/all-stages/scripts/run.sh prepare
bash repro-inputs/all-stages/scripts/run.sh fetch
bash repro-inputs/all-stages/scripts/run.sh up
bash repro-inputs/all-stages/scripts/run.sh image
```

每个阶段必须选择不同的新目录和容器，不能就地切换旧构建树。
`prepare` 拒绝已存在工作区；恢复程序也拒绝旧 tmp、编译输出或已恢复的阶段。
取源和构建容器禁网；不挂载旧 sstate、tmp、UniProton 库或原构建项目。

- Stage01：只执行 `prepare`，检查基线；没有 image/up 目标。
- Stage02：`fetch` / `image` 的目标为 `openeuler-image`。
- Stage03–Stage07：目标为 `tl3572-openeuler-mcs-image`。
- Stage05–Stage07：`up` 从完整归档重编内核库、依赖库及阶段 ELF，不执行旧脚本中的联网 clone。
- Stage07 `image` 只是 M6 系统基线加已实现 RPC 修复；不是全工业外设移交后的正式 M7 镜像。

完整有效的 MCS/内核树在容器项目的 `stage-sources/`；M5/M6 UniProton 工作树为
`src/UniProton/`，M7 为 `src/UniProton-m7/`，保留原构建路径。
Linux 日志收集器、systemd 模板、资源台账及其测试继续使用
`stages/stage07-peripheral-partition/` 中的原始文件，不虚构缺失的外设驱动。

## 真实性与验证边界

Stage03–Stage05 原始的独立完整历史层快照没有幸存；新增层是明确标注来源的重建版，
不能承诺与当时层目录逐字节一致。所有已经保留的实际源码、正式覆盖包、配方、
配置、依赖以及重建结果均上传；无法恢复的历史状态不冒充原始内容。

M5 boot 内嵌配置 SHA-256 为
`57e11529b3d8760c13eb0fa0093aa325157d59bd4176deea6f6198afd26b718d`，
其 CPU 政策是 `maxcpus=7`，并非 M6 的 `mcs_reserve_cpus=4-5`。

验证结果单独记录在 `tests/verification.md`。源码归档完整、离线取源通过、ELF 重编成功、
完整镜像重编成功及板上验收是不同结论，不能混用。
已完成七阶段独立恢复、Stage02–Stage07 离线取源，以及 M5 全新目录 ELF 重编与历史文件
逐字节一致；没有完成每个历史阶段的全镜像重编。此前 M6 全镜像、M6/M7 四份 ELF 和
M7 MCS/独立 micad 已干净重编，证据见 `../rk3572/tests/clean-rebuild.md`。

没有上传旧 tmp/sstate、大型生成镜像、密码/Token/私钥或 board core。
原厂 6.1 GiB Buildroot LinuxSDK 整体包、原厂 dl/sysroot 包仍未上传；它们没有参与
上述 openEuler 各 Stage 构建，其已使用的厂商源码/工具链/资产单独归档。
