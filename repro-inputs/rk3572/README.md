# RK3572 换机复现入口

本目录补齐 **TL3572 / RK3572 的当前 openEuler + MICA + 双 UniProton 构建**。
目标是从 GitHub 输入、固定基础容器和空构建目录得到内核、openEuler 镜像、
M6 双固件及 M7 已实现的软件切片；不是宣称所有历史阶段逐字节重建，
也不是宣称 M7 工业外设已验收。

## 实际构建在哪里

| 内容 | 原构建机实际位置 |
|---|---|
| 宿主机 / 容器 | `10.100.60.226` / `dev_openeuler` |
| 项目根目录 | `/home/openeuler/build/tl3572-2oo3` |
| 宿主机构建卷 | `/home/docker_space/docker/volumes/dev_openeuler_vol-openeuler-build/_data` → 容器 `/home/openeuler/build` |
| openEuler 包源码及 Yocto 层 | 项目内 `src/`；当前包含约 162 个目录，包括派生/验证副本 |
| 当前自定义 Yocto 层 | `meta-tl3572-stage3/`；名称仍为 stage3，内容已演进至 M6 |
| BitBake 配置 / 临时输出 | `build/build-tl3572/conf/` / `build/build-tl3572/tmp/` |
| 当前内核完整源码 | 上述层内 `recipes-kernel/linux/files/linux-6.12.69-v1.0-gf1b67c2.tar.gz` |
| UniProton / M7 副本 | `src/UniProton` / `src/UniProton-m7` |
| MCS 基线 / M7 副本 | `src/mcs` / `src/mcs-m7` |
| Arm GNU 14.3 | `toolchain-14.3/` |
| openEuler GCC 12.3 / Native SDK | `/usr1/openeuler/gcc/openeuler_gcc_arm64le` / `/opt/buildtools/nativesdk`，在固定基础镜像内 |
| 下载输入 / 当前 sstate | `/home/openeuler/build/downloads` / 项目内 `sstate-stage3/` |

原构建目录约 32 GiB；当前 sstate 约 1.1 GiB，中央 sstate 约 3.6 GiB。
它们是生成物/加速缓存，不是必须上传的输入，也不用于下面的干净复现。

## GitHub 必须保存的文件

1. `repro-inputs/stage01-05/upstream/`：七个固定提交的完整源码快照，
   含 Yocto/openEuler 元数据、UniProton、MCS、OpenAMP 和 libmetal，已在仓库。
2. `openeuler-packages.tar.gz`：另外 **150 个**已检出的 openEuler 软件包输入目录。
   包含实际源码压缩包、spec、补丁、许可证等；保留 `oee_archive` 实际使用的
   稀疏检出文件，不打包它约 745 MiB 的 Git 历史或未使用内容。
3. `downloads.tar.gz`：不由上述包目录提供的上游源文件和 Git 源码镜像压缩包。
   不含 `.done`、锁文件、宿主机凭据或活跃缓存的配置。
4. `uniproton-m6-complete-overlay.tar.gz`：实际 M6 源码改动、BSP、配置、
   `libboundscheck` 的完整有效源码、OpenAMP/libmetal 源码包及实际补丁。
   不含旧 `.a`、ELF 或构建目录。它覆盖七仓基线中的 UniProton 后即为 M6 有效输入；
   无需再重复套 Stage 05/06 的历史覆盖包。
5. `repro-inputs/meta-tl3572-stage3/`、`build-conf/`、`.oebuild/`：当前完整配方、
   所有内核补丁、内核源码、defconfig、设备树覆盖、厂商启动输入、镜像配置、
   M6 参考固件及校验，已在仓库。
6. `4-软件资料/Linux/Tools/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu.tar.gz`：
   原始交叉工具链，已在仓库；本目录脚本补齐原工作区的命令别名与空 `nosys.specs`。
7. `stages/stage07-peripheral-partition/`：M7 日志环/读取器、RPC 修复补丁、附加层、
   构建/测试脚本、资源划分和实机证据。外设直驱仍未完成。
8. 本目录 `scripts/`、`config/`、`SOURCE-INVENTORY.json`、`SHA256SUMS`：
   无密码的准备/构建入口、每个包的提交/状态及逐文件哈希。

归档的是有效工作树，不是所有仓库 Git 历史。`libboundscheck` 原先是未记录提交的
联网复制；现在冻结其每个文件的 SHA-256，不伪造一个不存在的提交记录。
未使用的通用 `src/kernel-5.10` 不进入当前链路；RK3572 实际使用的厂商
6.12.69 完整源码已保存。全量厂商 Buildroot SDK、旧 rootfs/update/ISO、
生成 sysroot、core dump、密码、Token、私钥不上传。

## 体积

| 上传内容 | 实测大小 |
|---|---:|
| 150 个 openEuler 包输入 | 491,581,163 B（468.81 MiB） |
| 必需的下载源镜像 | 12,401,338 B（11.83 MiB） |
| UniProton 完整有效源码覆盖 | 1,196,264 B（1.14 MiB） |
| 新增三个归档合计 | 505,178,765 B（481.78 MiB） |
| 清单、脚本和 M7 小型材料 | 约 3 MiB |
| 此前整个仓库的实际文件 | 约 2.63 GiB |
| 补齐后整个仓库实际文件总量 | **约 3.11 GiB（约 3.34 GB）** |

以上是当前文件内容，不等于 Git 历史、LFS 去重后的计费量或本地 `.git` 大小。
固定基础 Docker 镜像展开 **11,985,576,884 B（11.16 GiB）**，默认按摘要在线拉取，
不重复上传到 GitHub。镜像 registry 的压缩下载量另计，未将展开大小当作下载大小。
若需完全离线，还须单独保存/传递该基础镜像并验证 `docker load`；目前未把它分卷上传。

## 固定环境与换机命令

建议 Linux x86_64 或 Windows 的 x86_64 WSL2 Linux + Docker；
**把仓库与构建目录放在 Linux 原生文件系统**，不要在 Windows 挂载目录上执行 Yocto。
建议至少 8 核、32 GiB RAM、100 GiB 可用磁盘；原成功构建机为 64 线程/约 62 GiB RAM。
主机只需 Docker、Git、Git LFS；编译软件由镜像和仓库提供。

固定镜像：

```text
swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f
```

已在全新临时容器检查：Python 3.11.6、CMake 3.27.9、Git 2.43.0、
Native SDK、GCC 12.3.1 均由基础镜像直接提供；不是依赖原容器手工安装后的状态。
GCC 可执行文件 SHA-256 为
`0b2f6c2c7842e7839a233a8abda4f0ac4b92dcaa0580d6bacd90771c482a218a`。

```bash
git lfs install
git clone https://github.com/windchilly/TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1.git
cd TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1
git lfs pull
git lfs fsck

# 必须是尚不存在的新目录，不能指向原工作区。不要手工复用旧 tmp/sstate。
export REPRO_WORKSPACE="$PWD/../tl3572-fresh-build"
export REPRO_CONTAINER=tl3572-repro
export REPRO_JOBS=8
bash repro-inputs/rk3572/scripts/run.sh prepare
bash repro-inputs/rk3572/scripts/run.sh fetch
bash repro-inputs/rk3572/scripts/run.sh m6-up
bash repro-inputs/rk3572/scripts/run.sh m7-up
bash repro-inputs/rk3572/scripts/run.sh m6-image
bash repro-inputs/rk3572/scripts/run.sh m7-mcs
```

源码准备和编译容器用 `--network none`，配置用 `BB_NO_NETWORK=1`。
`OPENEULER_FETCH=disable` 只禁用包目录 Git 拉取/checkout；原 SRC_URI 映射仍执行，
从已校验的归档目录取真实源码。`SOURCE_DATE_EPOCH=1787652448` 来自固定
yocto-meta-openeuler 提交，避免无 `.git` 时退回当前时间。
下载 GitHub/LFS 和首次拉取容器仍需联网。

脚本固定**容器内部路径**，主机目录可自由选择；遇到已有项目不覆盖。
构建不需要访问开发板，不执行刷写、重启或外设控制。
`m6-up` / `m7-up` 为一次性干净构建入口；失败后先读日志，重新准备另一空目录，
不要运行历史脚本中的递归清理来覆盖旧工程。

## 产物与验收边界

- M6 ELF：`$REPRO_WORKSPACE/tl3572-2oo3/src/UniProton/demos/rk3572_mica/build/tl3572-m6-up-{a,b}.elf`。
- M7 ELF：相同路径将源码目录改为 `UniProton-m7`、文件名前缀改为 `tl3572-m7`。
- 内核、DTB、boot FIT、完整 rootfs：项目内 `build/build-tl3572/tmp/deploy/images/tl3572-evm/`。
- M7 MCS：`m7-mcs` 通过附加层构建含三份补丁的 MCS 包；不修改 M6 配方。

M6 镜像配方沿用已实机验证并校验固定哈希的参考双 ELF；它与另行从源码重编 ELF
是两条显式验证路径。不要直接覆盖配方中的参考 ELF，否则固定哈希检查会拒绝。
如要把新 ELF/M7 放进量产镜像，需另立配方/更新验证清单后重新实机验收。
构建时间、DWARF 路径等可能改变二进制哈希，本入口不承诺历史输出逐字节一致。

### 当前验证状态

输入导出、归档哈希、固定容器的 SDK/工具链检查已通过。
独立空目录的离线构建检查正在进行；以 `tests/clean-rebuild.md` 记录的具体结果为准。
不能把“源码已上传”或“fetch 通过”当成完整镜像重建通过。
Stage 03/04/05 未找到每阶段未修改的完整独立层快照；历史差异保留在阶段材料中，
本次保证范围为当前 M6/M7 软件输入链路，不改写这一历史限制。
