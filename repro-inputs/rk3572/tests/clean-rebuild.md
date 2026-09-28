# RK3572 独立复现检查（2026-09-28）

状态：源码/环境准备、M6/M7 双固件、完整 M6 镜像、M7 MCS 软件包及独立 micad 均已通过。
全部编译使用固定基础镜像、新工作目录与断网容器；新产物未部署到板卡。

## 隔离条件与 GitHub 下载

- 基础镜像摘要沿用 Stage 01，镜像 ID `ed46fbc8a8ec...`；无旧容器的可写层。
- 新基础容器已确认 SDK、GCC 12.3、Python 3.11.6、CMake 3.27.9 可用。
- 在 Windows 临时目录独立克隆 GitHub，使用 Git LFS 3.7.1 下载所有构建所需
  LFS 文件；四个新增归档、SOURCE-INVENTORY、完整内核、Arm 工具链哈希全部一致。
- Linux 测试源码同样从 GitHub 克隆。为避免基础镜像旧 Git LFS 2.10 的慢下载，
  使用 `restore_verified_input_cache.py` 按**已提交 LFS 指针的 SHA-256/大小**注入
  上传端的源码归档缓存：21 个文件全部匹配。没有从旧编译目录复制 `.a`、sysroot
  或 sstate。独立 Windows 下载进一步确认相同对象可从 GitHub 取回。
- 所有编译容器 `--network none`，BitBake `BB_NO_NETWORK=1`。
- 检查归档的完整内核源码：不含 `.o`、`.a`、`.ko`、`Image`、`vmlinux`
  或 `Module.symvers` 等旧构建输出；此次重新生成内核和管理模块。
- 源码挂载 `/repo` 只读；工作卷只挂载新目录到 `/home/openeuler/build`。
- 固件检查工作目录 `tl3572-github-repro-20260928/work-v3`、容器
  `tl3572-repro3-20260928`；最终镜像检查使用另一个全空 `work-v4`、容器
  `tl3572-repro4-20260928`，源码提交 `5655fb0`。
- 上述目录均在原宿主机构建卷中，但不挂载原项目的 tmp/sstate/生成库。
  这验证的是同一宿主机上的全新隔离环境；没有声称已在另一台物理机器上运行。

## 干净检查补齐的隐含输入

1. 原 UniProton 脚本联网获取 libboundscheck、OpenAMP/libmetal；改为归档实际源码。
2. 工具链原人工创建 none-elf 命令别名及空 nosys.specs；准备脚本显式恢复。
3. Native SDK 环境必须 source，否则 `compile_et` 不在 PATH。
4. lwIP 2.1.3 原来由 CMake 隐式 FetchContent；归档完整实际适配后的源码。
5. os-base/systemd 确实读取 Git 提交/时间；恢复精确单提交浅 Git 数据和空 refs 目录，
   不使用伪造提交，不包含原 remote、hooks 或凭据。
6. neard、erofs-utils 原只有裸 Git 下载缓存，没有镜像 tar；补齐独立、去 remote/hooks
   的源码镜像。活跃配置未用到 FatFs ff15，不伪称已取得其历史检出树。

## M6 / M7 固件：通过且与实机版本逐字节一致

均从源码重编核心库、libboundscheck、libmetal、OpenAMP、BSP 和最终 ELF，
命令退出为 0；没有复用旧 .a 或 ELF。已知上游 endian 运算括号与 RTOS RWX LOAD
段等 warning 仍在，不能称整个 UniProton 编译零 warning。

| 固件 | SHA-256，与仓库参考版本相同 |
|---|---|
| M6 UP1 | `9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8` |
| M6 UP2 | `3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4` |
| M7 UP1 | `e42b1a37ab460d34943ae0bd825f72cd5cbdcfc5efd0a2db00b156088738c5bf` |
| M7 UP2 | `d51461363145044ca6a1b498d301a54c218770a7a4175ef2528d28f62817b47a` |

原始检查日志位于固件工作卷根目录 `m6-up.log`、`m7-up.log`，并保存到
[M6 编译日志](logs/m6-up.log)、[M7 编译日志](logs/m7-up.log)。
M7 日志读取器的五项本地单测也通过；没有刷写板卡、重启板卡或追加物理外设测试。

## 当前完整 M6 镜像：离线取源、编译与打包通过

最终源码镜像补齐后，在新的 work-v4 中执行准备和取源；
`bitbake tl3572-openeuler-mcs-image --runall=fetch`：
**224/224 全部成功，0 个复用的取源任务，FETCH_RESULT=0**。
可下载 [准备日志](logs/prepare.log) 与 [离线取源日志](logs/fetch.log)；
原始日志的校验清单为 [logs/SHA256SUMS](logs/SHA256SUMS)。

随后执行 `m6-image`，结果为：
**2920/2920 任务全部成功，M6_IMAGE_RESULT=0**；其中 224 个取源任务已由上一步完成，
不需重复运行，不能将它们误称为复用了原工作区的编译产物。
初始 sstate 统计为 `Wanted 1329 Local 0 Mirrors 0 Missed 1329 Current 0`，
即旧编译缓存命中率为 0%。内核 Image、管理模块、设备树覆盖及 boot FIT 的
配方校验均通过，完整 rootfs 的 RPM 安装和 ext4/tar.gz 打包通过。
BitBake 汇总为 **6 个 WARNING**：python3-setuptools-native、systemd、openssh
三个上游补丁的 fuzz/QA 警告；内核等具体编译中的警告也保留在原始日志中。
没有把历史缓存构建的“零 warning”沿用到本次。

证据：[镜像构建日志](logs/m6-image.log)、[完整内核编译日志](logs/kernel-compile.log)、
[本轮内核/FIT/模块产物哈希](logs/kernel-artifacts.sha256)、
[rootfs 包版本清单](logs/rootfs-packages.manifest)。这些镜像输出保留在独立工作卷，
未重复上传到 GitHub；上传的是完整构建输入、过程和验证记录。

本轮 rootfs 产物位于 `build/build-tl3572/tmp/deploy/images/tl3572-evm/`：

| 稳定链接名 | 大小 | 本轮 SHA-256 |
|---|---:|---|
| `tl3572-openeuler-mcs-image-tl3572-evm.ext4` | 4,294,967,296 B，稀疏文件逻辑大小 | `516da22813070eb37e1777df517e2073549c5dc259a23d251c63f360a70de6f3` |
| `tl3572-openeuler-mcs-image-tl3572-evm.tar.gz` | 90,220,064 B | `8f753eb8e6905d02e49beea3c224dcd10b8761f6d689ea79c80b916b5c6d2def` |

## M7 MCS 软件包：三份补丁实际编译、RPM 生成通过

镜像成功后在同一个新工作区执行 `m7-mcs`：
**147/147 任务全部成功，M7_MCS_RESULT=0**。131 个依赖任务复用的是刚刚完成的
本轮 M6 构建，MCS 自身重新取源、应用补丁、编译、安装、做 QA 并生成 RPM。
BitBake 汇总有 2 个 mcs-linux `patch-fuzz` WARNING，保留而不屏蔽。

已将实际编译的两个 RPC 源文件与此前板卡回归使用的 `src/mcs-m7` 源码比较，
SHA-256 完全一致，引用计数及失败清理实际进入新构建：

- `rpc_backend.c`：`04e6c8151315a1f016230da13b4cc62a2d55c0cee92b5f0ceaa65f8eea7aef5e`。
- `rpmsg_rpc.c`：`1f8a623974f14144aa05f4a453551d9cfd4a33850bcc4ee877699fde1f64b0e4`。

证据：[M7 MCS 总日志](logs/m7-mcs.log)、[补丁日志](logs/m7-mcs-patch.log)、
[编译日志](logs/m7-mcs-compile.log)。这是单独软件包，不是完整 M7 镜像；
没有把新 RPM 安装到板卡，也没有把该补丁自动替换进上述 M6 rootfs。

## 板卡独立部署版 micad：干净依赖库重建与字节一致性通过

在上述全新工作区内，按 Stage07 已有脚本准备 `src/mcs-m7`，并用本轮 M6 构建
生成的 libmetal/OpenAMP/sysfsutils 依赖库运行 `build_m7_micad.sh`。
**M7_MICAD_STANDALONE_RESULT=0**，生成 `build-micad-m7/mica/micad/micad`：
SHA-256 为 `40b7791d55ea58edb92d0119bd985ad560b2d3e1a1eba26ed1aa6566f907d20c`，
与仓库保存、板卡 40 轮回归通过的独立部署版本完全一致。
readelf 确认 PIE、GNU_RELRO、BIND_NOW，未出现 RPATH/RUNPATH；导入 `__stack_chk_fail`。
已知上游 UMT 未使用变量 warning 仍在。原始日志见
[独立 micad 构建日志](logs/m7-micad-standalone.log)。此处也没有访问或部署到板卡。

## 边界

M6/M7 四份 ELF 与独立修复版 micad 在此次环境中实际达到字节一致；完整 rootfs/boot FIT 已成功生成，
不承诺与历史镜像或后续重建逐字节一致。上表及内核产物清单记录本轮输出，
不是对其他构建日期的固定二进制验收哈希。历史 Stage 03–05 没有各自未修改的
完整独立层快照，仍不能声称每个历史阶段均可独立重建。
M7 工业外设直驱未完成，本次上传/重编不是 M7.0 验收。
