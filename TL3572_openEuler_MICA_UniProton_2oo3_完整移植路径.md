# TL3572-EVM openEuler Embedded + MICA + 三 UniProton 2oo3 完整移植路径

文档版本：V1.5  
编制日期：2026-09-14  
最近验证：2026-09-21  
目标硬件：TL3572-EVM / Rockchip RK3572 / 4 GiB RAM  
目标形态：openEuler Embedded 作为主系统，MICA bare-metal 管理三个 UniProton 实例，三个实例执行相同控制逻辑，任意两个输出一致即通过（2oo3，2-out-of-3）。

> 本文档截至“三个 UniProton 同芯片 2oo3 功能原型验证完成”为止。它不等同于 IEC 61508/SIL 功能安全认证，也不能覆盖 SoC、DDR、电源、时钟和单一表决器等共因故障。

## 1. 最终架构

```text
RK3572 Loader / U-Boot / TF-A（保留厂商启动链）
                    │
                    ▼
厂商 Linux 6.12.69 + TL3572 DTB + MICA/MCS 适配
                    │
                    ▼
openEuler Embedded systemd rootfs
                    │
          ┌─────────┴─────────┐
          │ micad / MICA      │
          │ 输入代理 / 表决器 │
          │ 唯一 I/O 代理     │
          └─────────┬─────────┘
                    │ OpenAMP / RPMsg
        ┌───────────┼───────────┐
        ▼           ▼           ▼
  UniProton A  UniProton B  UniProton C
      CPU3          CPU4          CPU5
        └───────────┬───────────┘
                    ▼
        2oo3 多数表决 → 现场输出
```

上图采用默认资源优先方案（CPU3/4/5 均为 A53）；若阶段8决策要求三个不同 CPU
cluster 的故障域隔离，则切换为 CPU3/5/7，具体见 `7.4` 和 `10.1`。

总实施路径：

```text
阶段0 已验证恢复基线
  → 阶段1 使用远程构建环境
  → 阶段2 openEuler rootfs 在 TL3572 启动
  → 阶段3 建立 meta-tl3572 BSP 层
  → 阶段4 Linux 6.12 MICA/MCS 适配
  → 阶段5 单 UniProton
  → 阶段6 双 UniProton 多实例（已完成）
  → 阶段7 三 UniProton 多实例
  → 阶段8 确定性输入、状态和输出协议
  → 阶段9 2oo3 表决与 I/O 仲裁
  → 阶段10 故障注入和验收
```

## 2. 当前已验证基础

### 2.1 TL3572-EVM

- 当前完整厂商 `update.img` 已在 Loader 模式下重新烧录并验证恢复启动。
- 当前可工作的厂商系统为 Buildroot 2026.02.2。
- 当前厂商内核为 `6.12.69-gf1b67c293213`。
- 当前根分区为 `/dev/mmcblk0p6`，OEM 为 `/dev/mmcblk0p7`，userdata 为 `/dev/mmcblk0p8`。
- 当前 CPU 拓扑：
  - CPU0～3：Cortex-A53，cluster 0；
  - CPU4～5：Cortex-A53，cluster 1；
  - CPU6～7：Cortex-A73，cluster 2（实机 MIDR `0x411fd090`，part `0xd09`）。
- 当前内核已经启用 RPMsg、RPMsg VirtIO、Rockchip mailbox RPMsg、PSCI、CPU hotplug 和 reserved-memory。
- 当前内核尚未启用 `CONFIG_REMOTEPROC`、`CONFIG_RPMSG_CHAR`、`CONFIG_RPMSG_CTRL`。
- 当前 DTB 尚无 MICA 所需 RTOS 专用保留内存。

### 2.2 远程构建服务器验证结果

初次验证：2026-09-14  
最近复核：2026-09-15  
服务器：`10.100.60.226`

| 项目 | 验证结果 |
|---|---|
| 宿主机 SSH `22/tcp` | 可达并登录成功 |
| Euler Docker SSH `2005/tcp` | 可达并登录成功 |
| 容器名称 | `dev_openeuler` |
| 容器 SSH 用户 | `openeuler` |
| 宿主系统 | openEuler 24.03 LTS-SP2，x86_64 |
| 容器系统 | openEuler 24.03 LTS-SP2，x86_64 |
| CPU | 64 个逻辑 CPU |
| 内存 | 64 GB（容器实测总量 61 GiB/61.9 GiB，可用约 54 GiB） |
| Swap | 31 GiB |
| 构建卷可用空间 | 约 577 GiB |
| Docker | 26.1.4 |
| Python | 3.11.6 |
| GCC | 12.3.1 |
| oebuild | `/usr/local/bin/oebuild`，命令可正常运行 |
| AArch64 工具链 | `/usr1/openeuler/gcc/openeuler_gcc_arm64le` |
| openEuler 源码 | `/usr1/openeuler/src` |
| 用户构建目录 | `/home/openeuler/build`，可读写 |
| 容器镜像 | `openeuler-container:latest`，已锁定镜像摘要见阶段1 |

> 2026-09-15 宿主机 `docker inspect` 显示 `dev_openeuler` 没有单独设置 Docker memory/cpuset 硬限制（`MemoryBytes=0`、`CpusetCpus`为空）；容器当前可使用宿主机约 64 GB 物理内存，`docker stats` 显示上限为 61.9 GiB。本文所称“分配64G”指该可用资源上限，而不是 Docker 的硬配额。

直接进入构建容器：

```bash
ssh -p 2005 openeuler@10.100.60.226
```

仅在需要查看 Docker 状态、重启容器或处理挂载时才登录宿主机：

```bash
ssh root@10.100.60.226
```

登录参数如下：

| 目标 | 地址 | SSH端口 | 用户名 | 认证 |
|---|---|---:|---|---|
| openEuler宿主机 | `10.100.60.226` | 22 | `root` | 凭据仅在本地保存，不入库 |
| `dev_openeuler`容器 | `10.100.60.226` | 2005 | `openeuler` | 凭据仅在本地保存，不入库 |

> 注意：容器SSH禁止root直接登录；连接2005端口时必须使用`openeuler`用户。

### 2.3 远端已有可复用内容

远端已经存在：

```text
/home/openeuler/build/build-mcs
/home/openeuler/build/build-rk3588-uniproton-mica-20260820
/usr1/openeuler/src/yocto-meta-openeuler
/usr1/openeuler/src/UniProton
/usr1/openeuler/src/mcs
/usr1/openeuler/src/OpenAMP
/usr1/openeuler/gcc/openeuler_gcc_arm64le
```

阶段1另已建立独立产品工作区：

```text
/home/openeuler/build/tl3572-2oo3
```

其中：

- `build-mcs/compile.yaml` 是 `qemu-aarch64 + openamp + mcs` 的 host 构建配置，可作为配置参考；
- 已有一份 RK3588 UniProton/MICA 适配工作目录，是 RK3572 移植最有价值的参考；
- `yocto-meta-openeuler` 当前为 `openEuler-26.03` 分支；
- 多个源码目录含已有未提交修改。

因此执行约束如下：

1. 不在上述已有源码树直接切分支、清理、覆盖或执行 `git reset`；
2. 不执行 `bitbake -c cleanall`、`cleansstate` 等可能影响共享成果的命令；
3. TL3572 开发必须建立独立源码目录、独立 build 目录和独立 TMPDIR；
4. 可以只读参考 RK3588 适配、复用现有交叉工具链；
5. `DL_DIR` 和 `SSTATE_DIR` 可以共享，但需确认没有并行清理任务；
6. 每次修改前先保存目标仓库的分支、HEAD、`git status` 和补丁快照。

## 3. 阶段0：恢复基线

### 当前状态

阶段0已经完成，不再扩展其他备份工作。

唯一验收条件：

> 完整厂商 `update.img` 可以在 Loader 模式下重新烧录，并恢复正常启动。

验证结果：**通过**。

阶段状态：`COMPLETE`。

## 4. 阶段1：使用可重复的 openEuler 构建环境

本阶段使用 `10.100.60.226:2005` 上的 `dev_openeuler`，不再搭建本地 Ubuntu/WSL/Docker，也不执行 QEMU 基线构建或启动。

验证时间：2026-09-15  
阶段状态：`COMPLETE`

### 4.1 登录与环境实测

```bash
ssh -p 2005 openeuler@10.100.60.226

whoami
cat /etc/os-release
nproc
free -h
df -h /home/openeuler/build
oebuild --version
```

实测结果：

| 项目 | 结果 |
|---|---|
| 用户 | `openeuler` |
| 系统 | openEuler 24.03 LTS-SP2，x86_64 |
| CPU | 64个逻辑CPU |
| 内存 | 64 GB标称；容器显示61 GiB/61.9 GiB，总可用约54 GiB |
| Swap | 31 GiB |
| 构建卷 | ext4，约1.7 TiB，剩余578 GiB |
| oebuild | `0.2.1.2` |
| Python | `3.11.6` |
| Git | `2.43.0` |
| CMake/Ninja | `3.27.9` / `1.11.1` |
| BitBake | `2.0.0` |
| Native SDK | `/opt/buildtools/nativesdk`，存在且可读 |
| AArch64 GCC | `aarch64-openeuler-linux-gnu-gcc 12.3.1 20230508` |

Docker宿主侧复核：

```text
容器ID：6f47adafeaa381eacc2898bfcc2a8fb7828f162b6d8d08c9d356a96d212c18f7
镜像ID：sha256:ed46fbc8a8ecb67c87b2fc46439aea1e50b4712d404ed4c00e57a471f505f887
镜像摘要：swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f
Docker MemoryBytes：0
Docker CpusetCpus：空
```

`MemoryBytes=0`和空的`CpusetCpus`表示没有额外的容器硬限制；该容器当前可以使用宿主机约64 GB内存和64个逻辑CPU。复现环境时必须使用上面的镜像摘要，不能只记录浮动的`latest`标签。

### 4.2 已建立的TL3572独立工作区

实际目录：

```text
/home/openeuler/build/tl3572-2oo3/
├─ .oebuild/           # 独立oebuild配置
├─ src/                # 独立、干净、固定提交的源码
│  ├─ yocto-meta-openeuler/
│  ├─ yocto-poky/
│  ├─ yocto-meta-openembedded/
│  ├─ mcs/
│  ├─ UniProton/
│  ├─ OpenAMP/
│  └─ libmetal/
├─ meta-tl3572/        # TL3572 Yocto BSP层
├─ build-rootfs/       # openEuler rootfs构建
├─ build-kernel/       # 厂商Linux/MICA构建
├─ build-uniproton/    # UniProton A/B/C构建
├─ images/             # boot/rootfs/update镜像
├─ deploy/             # 板卡部署文件
├─ logs/               # 构建与串口日志
├─ test/               # 自动测试和故障注入
└─ manifests/          # 版本、哈希、配置清单
```

`oebuild 0.2.1.2`不允许直接在已有`/home/openeuler/build/.oebuild`工作区的子目录执行嵌套`init`。本次验证采用“外部初始化后移动到构建卷”的方式：

```bash
test ! -e /home/openeuler/tl3572-2oo3-init
test ! -e /home/openeuler/build/tl3572-2oo3

cd /home/openeuler
oebuild init \
  -u https://atomgit.com/openeuler/yocto-meta-openeuler.git \
  -b openEuler-24.03-LTS \
  /home/openeuler/tl3572-2oo3-init

mv /home/openeuler/tl3572-2oo3-init \
   /home/openeuler/build/tl3572-2oo3

cd /home/openeuler/build/tl3572-2oo3
oebuild update yocto
oebuild update layer
```

初始化后不要再次无条件执行全量`oebuild update`，因为它会更新源码并处理浮动容器标签。需要更新时先保存清单和补丁，并分别执行受控的`update yocto`或`update layer`。

### 4.3 已锁定的版本基线

| 组件 | 固定提交或版本 |
|---|---|
| yocto-meta-openeuler | `3aa6999c9ab78569bc2209a9dbb185e2f7e4301c`（`openEuler-24.03-LTS`） |
| yocto-poky | `4bf0e3ea7a5cd4577ae43c510870f235a39eedc0`（清单版本`v4.0.10`） |
| yocto-meta-openembedded | `a82d92c8a6525da01524bf8f4a60bf6b35dcbb3d`（清单版本`dev_kirkstone`） |
| MCS/MICA | `5cb49156276be04d54a77a630b8600dcc122fdba` |
| UniProton | `1d102888822449b8205894db4f483abc71c0d05b` |
| OpenAMP | `5fbe563479c2c137a442659e87f603dd323a03c3` |
| libmetal | `69e96d9620652df428ec7f4faca92f70cce111d3` |
| oebuild | `0.2.1.2` |
| BitBake | `2.0.0` |
| AArch64工具链 | GCC `12.3.1 20230508` |
| 厂商Linux源码包SHA256 | `186FACE3889200078EF67A8D97F1ED587E4E1D1E30683A81566D5E85A2D60608` |

七个独立源码仓均已检查为干净工作树。24.03 LTS的`.oebuild`清单固定MCS、OpenAMP和libmetal提交；UniProton使用远端RK3588参考树的上游提交建立干净副本，原参考树中的未提交修改只作为后续移植参考，不进入可重复基线。

完整清单同时保存为：

```text
本地：`stages/stage01-baseline/TL3572-stage01-baseline-manifest.md`
远端：/home/openeuler/build/tl3572-2oo3/manifests/stage1-baseline.md
```

已有`/usr1/openeuler/src`、`build-mcs`和RK3588工作区继续保持只读参考；阶段1完成后复核，其HEAD与未提交状态均未改变。

### 4.4 工具链和构建能力验证

实际使用以下编译器完成最小链接测试：

```text
/usr1/openeuler/gcc/openeuler_gcc_arm64le/bin/aarch64-openeuler-linux-gnu-gcc
```

输出文件验证结果：

```text
ELF 64-bit LSB PIE executable
Machine: AArch64
Interpreter: /lib64/ld-linux-aarch64.so.1
TOOLCHAIN_SMOKE=PASS
```

同时验证：

- `oebuild generate -l`能够列出`systemd`与`mcs`特性；
- openEuler 24.03 LTS支持`qemu-aarch64/ok3568`等MCS平台，但没有TL3572，后续必须建立`meta-tl3572`；
- Native SDK环境脚本存在；
- BitBake命令可执行；
- 共享`/home/openeuler/build/downloads`和`sstate-cache`可读写；
- 未运行QEMU构建、启动或任何板级镜像构建。

### 4.5 64GB内存下的缓存与并发策略

为TL3572配置：

```text
独立 build、tmp、work、deploy
共享 /home/openeuler/build/downloads
共享 /home/openeuler/build/sstate-cache，但禁止清理他人缓存
BB_NUMBER_THREADS：初始32
PARALLEL_MAKE：初始-j32
```

虽然现在有64逻辑CPU和约64 GB内存，首次构建仍不直接使用64并发。建议从32并发开始；持续观察`MemAvailable`、load、I/O wait和OOM日志，在可用内存长期高于16 GiB且无换页压力时，可试升至36～40。出现Swap持续增长、单任务被OOM kill或磁盘I/O拥塞时，回退到24～32。

### 4.6 阶段验收结果

| 验收项 | 结果 |
|---|---|
| 容器SSH直接登录 | `PASS` |
| `/home/openeuler/build`可写、源码可读 | `PASS` |
| TL3572独立工作区建立 | `PASS` |
| openEuler 24.03 LTS及依赖层固定 | `PASS` |
| MCS、UniProton、OpenAMP、libmetal固定 | `PASS` |
| AArch64编译和链接 | `PASS` |
| Native SDK、BitBake、oebuild可执行 | `PASS` |
| 共享下载与sstate缓存可读写 | `PASS` |
| 现有RK3588和MCS成果未被修改 | `PASS` |
| 未进行QEMU验证 | `PASS` |

阶段结论：**通过，阶段1完成。**

实际验证和工作区初始化约15分钟；计划工期仍保留0.5天，用于新服务器上复现时处理网络和权限差异。

## 5. 阶段2：openEuler rootfs 在 TL3572 启动

本阶段只替换 rootfs，不启用 UniProton，不修改 Loader/U-Boot/Recovery。

### 5.1 生成 systemd rootfs

镜像至少包含：

- systemd；
- systemd-networkd或项目指定网络管理组件；
- OpenSSH；
- bash、coreutils、util-linux；
- kmod、iproute2、ethtool；
- e2fsprogs、dosfstools；
- strace、gdbserver、perf按需加入；
- MICA用户态组件预留，但默认不自动启动RTOS。

### 5.2 合并厂商内核模块和固件

必须与当前内核严格匹配：

```text
/lib/modules/*.ko
/lib/firmware
必要的Rockchip GPU/NPU/VPU、显示、摄像头、Wi-Fi/BT固件
```

当前厂商Buildroot使用扁平的`/lib/modules/*.ko`布局，并由板级脚本直接`insmod`。阶段2保留该布局，逐个以`modinfo -F vermagic`确认其值为`6.12.69-gf1b67c293213 SMP mod_unload aarch64`；不得擅自移动到版本目录后假设原厂加载脚本仍然有效。

厂商用户态二进制库不能整目录覆盖。逐个检查 ELF 解释器、glibc需求、RPATH、SONAME和依赖。

### 5.3 配置启动系统

- 根分区：`/dev/mmcblk0p6`；
- OEM：`/dev/mmcblk0p7`；
- userdata：`/dev/mmcblk0p8`；
- 串口：`ttyFIQ0`，实测波特率`115200 8N1`；
- 开启串口getty；
- 配置网口和SSH；
- 配置hostname、时区、DNS；
- 系统启动不能依赖暂未适配的MICA组件。

### 5.4 制作 rootfs.ext4

检查：

- 镜像尺寸小于rootfs分区；
- UUID和fstab一致；
- root用户和SSH策略符合测试要求；
- 文件权限、符号链接、capability正确；
- 厂商扁平布局中的`/lib/modules/*.ko`其`vermagic`与`uname -r`完全一致。

### 5.5 只烧rootfs分区

通过RKDevTool只更新rootfs，保留：

```text
Loader、GPT、U-Boot、boot、recovery、oem、userdata
```

### 5.6 验收

1. 串口进入systemd；
2. `uname -a`仍为厂商Linux 6.12.69；
3. rootfs识别为openEuler Embedded；
4. 网口、SSH正常；
5. 关键模块加载正常；
6. 冷启动10次；
7. 运行24小时；
8. 出错时可重新烧写完整厂商 `update.img` 恢复。

产物：

```text
rootfs-openeuler-tl3572.ext4
rootfs.manifest
rootfs.sha256
boot-log-rootfs-stage.txt
```

预计：1～3天。

### 5.7 2026-09-15构建与实机验证记录

阶段状态：`PARTIAL_PASS`。rootfs构建、单分区烧录、启动、网络、SSH和`mcsctl`用户态入口均已通过；`proc-fs-nfsd.mount`与`auditd.service`清理、冷启动10次和24小时运行仍未完成，暂不进入阶段3。`findmnt`、`ss`、`getent`等中等及以上价值的诊断工具经决策统一并入阶段3 BSP镜像，不再作为阶段2收口阻塞项。

最新合并修正版烧录产物（包含网络修复和`mcsctl`修复）：

```text
本地归档：
`stages/stage02-rootfs/release-mcsctl-20260915/rootfs-openeuler-tl3572-mcsctl.ext4.gz`

远程构建机BitBake原始输出：
/home/openeuler/build/tl3572-2oo3/build/build-rootfs/tmp/deploy/images/qemu-aarch64/openeuler-image-qemu-aarch64-20260915082322.rootfs.ext4

解压后逻辑大小：4294967296 bytes
构建日志：`stages/stage02-rootfs/release-mcsctl-20260915/build.log`
文件系统检查：`stages/stage02-rootfs/release-mcsctl-20260915/e2fsck.txt`
追加配方：`stages/stage02-rootfs/release-mcsctl-20260915/mcsctl.bbappend`
```

文件名中的`qemu-aarch64`来自阶段2所用的Yocto配置`MACHINE=qemu-aarch64`，只表示以该机器配置生成通用AArch64 openEuler用户态种子，并不表示TL3572运行QEMU。当前阶段继续保留厂商Loader、GPT、U-Boot、`boot.img`、Linux 6.12.69内核和设备树，排除了QEMU 5.10内核模块，再由`meta-tl3572`注入厂商模块/固件和板级配置。该文件只能烧写`rootfs`分区，不能作为整机固件覆盖`boot`、`uboot`或Loader。阶段3建立正式`MACHINE=tl3572-evm`后再消除该过渡命名。

RKDevTool只烧写`rootfs`，地址`0x0007a000`；Loader、GPT、U-Boot、boot、recovery、oem和userdata均未更新。115200串口日志确认DDR训练、SPL、TF-A、OP-TEE、U-Boot、厂商FIT内核和systemd启动链完整。

| 验收项 | 实测结果 | 状态 |
|---|---|---|
| 串口进入systemd | 出现`openEuler Embedded 24.03-LTS tl3572-openeuler ttyFIQ0`并可用root登录 | `PASS` |
| 系统身份 | `openEuler Embedded 24.03-LTS`，`OEE_REVISION=3aa6999c...` | `PASS` |
| 厂商内核保持不变 | `6.12.69-gf1b67c293213` | `PASS` |
| 根分区 | `/dev/mmcblk0p6`，ext4，读写挂载 | `PASS` |
| 数据分区 | `/dev/mmcblk0p7 -> /oem`，`/dev/mmcblk0p8 -> /userdata` | `PASS` |
| 有线网络 | `eth0`链路100 Mbps；修正1后仅由systemd-networkd管理，单一DHCP地址、默认路由、DNS和SSH均正常 | `PASS` |
| SSH | OpenSSH 9.3；合并修正版烧录后DHCP地址为`192.168.2.144`，Windows侧ICMP及TCP/22实测通过 | `PASS` |
| 厂商模块资源 | 7个Wi-Fi/BT模块存在，权限0644，vermagic全部匹配6.12.69 | `PASS`（尚未逐个加载） |
| MICA用户态预置 | `/usr/bin/mcsctl -> mica`已固化进RPM和rootfs，`mica --help`与`mcsctl --help`均可用；`micad`保持disabled/inactive且未启动RTOS | `PASS`（阶段2范围） |
| 冷启动10次 | 未执行 | `PENDING` |
| 连续运行24小时 | 未执行 | `PENDING` |

实机发现的镜像问题，必须在阶段2收口构建中修正：

1. **`RESOLVED`，2026-09-15：** `/etc/systemd/network/10-eth-static.network`与项目的`20-wired.network`曾同时存在，且`dhcpcd.service`处于enabled/active，造成`eth0`同时出现`192.168.7.2`、`192.168.2.142`和`192.168.2.143`。现已通过`os-base_%.bbappend`从包源删除旧静态配置，通过`dhcpcd_%.bbappend`禁止服务自动启用，并在镜像后处理阶段清除遗留enablement。双网口的`systemd-networkd-wait-online`改为`--any --timeout=30`，只接任一路网线不会再超时失败。修正已固化到最新合并镜像并完成实机烧录：`eth0`只取得`192.168.2.144/24`和一个默认路由；`systemd-networkd/resolved`为active，`dhcpcd`为inactive/disabled，wait-online为active/exited；网关双包0%丢包，公网域名`www.openeuler.org`解析及访问成功，Windows到板卡ICMP和TCP/22复测通过。
2. **`RESOLVED`，2026-09-16：** `auditd.service`已在阶段3 M1镜像中移除（audit 包保留但无失败单元）。`proc-fs-nfsd.mount`在阶段3 M2中彻底解决：`NO_RECOMMENDATIONS=1`拦不住 nfs 系包，因为共有三条硬依赖路径，全部通过 `meta-tl3572-stage3` 的 packagegroup bbappend `:remove` 封堵——①`packagegroup-network`→`packagegroup-network-nfs`；②`packagegroup-base`（distro nfs 特性）→`packagegroup-base-nfs`（连带 rpcbind）；③`packagegroup-core-full-cmdline-sys-services`→`nfs-utils`+`rpcbind`（该路径由镜像 feed 内 `dnf repoquery --whatrequires` 反查发现）。另在镜像后处理中加入`/etc/systemd/system/proc-fs-nfsd.mount -> /dev/null` mask 兜底。重建后 manifest 中 nfs/rpcbind 包计数为 0，rootfs 内已无任何 nfs systemd 单元。
3. **`RESOLVED`，2026-09-15：** 根因是openEuler 24.03-LTS配方/RPM名称为`mcsctl`，但上游`micactl`的Python console entry point只生成`mica = mica:main`，因此原镜像虽然安装了`mcsctl-1.0-r0`包，却只有`/usr/bin/mica`。项目新增与无版本号上游配方精确匹配的`recipes-mcs/mcs-linux/mcsctl.bbappend`，在`do_install:append()`中创建相对软链接`/usr/bin/mcsctl -> mica`并将其纳入`${PN}`。增量构建2829个任务全部成功，RPM清单、最终rootfs和离线`e2fsck`均通过；烧录`openeuler-image-qemu-aarch64-20260915082322.rootfs.ext4`后，实机确认该软链接为镜像内置，`mcsctl --help`正确列出`create/start/stop/rm/status/gdb`。`micad`仍为disabled/inactive，这是阶段2禁止RTOS自动启动的预期状态；在阶段4完成内核MCS适配前，不把`mcsctl status`成功作为本阶段验收条件。
4. **`DEFERRED_TO_STAGE3`，2026-09-16：** 设置`NO_RECOMMENDATIONS=1`后，`findmnt`、`ss`和`getent`等拆分子包未进入阶段2镜像。三者分别用于挂载拓扑、Socket/监听端口和NSS/DNS诊断，不影响当前启动、网络或MICA用户态预置结论。已确认对应Yocto包为`util-linux-findmnt`、`iproute2-ss`、`glibc-external-utils`，统一在阶段3的正式`tl3572-openeuler-mcs-image`中显式加入。
5. 当前root空密码、`PermitRootLogin yes`、`PasswordAuthentication yes`、`PermitEmptyPasswords yes`仅用于阶段2实验室调试；正式镜像必须改为密钥或强密码策略。

## 6. 阶段3：建立 meta-tl3572 BSP层

阶段状态：`COMPLETE`（2026-09-16）。M1 构建+实机验收、M2 nfs 清理、完整 update.img 生成与整镜像实机烧录复验（`systemctl --failed` 归零）全部通过。冷启动 10 次与 24 小时稳定性测试经决策延后，与阶段 4 验证合并执行。

2026-09-16已完成里程碑M1的离线验收：建立正式`MACHINE=tl3572-evm`、
`meta-tl3572`层和`tl3572-openeuler-mcs-image`配方，2845个BitBake任务全部成功；
输出4 GiB的TL3572专用ext4镜像，`e2fsck -fn`五阶段检查通过且文件系统状态为
`clean`。镜像已包含`mcsctl`、`findmnt`、`ss`、`getent`、systemd-networkd
DHCP配置、7个厂商内核模块和68个固件文件，且不含通用5.10内核模块。
`auditd.service`已不存在，`proc-fs-nfsd.mount`仍为已知遗留项。

本里程碑仍沿用已验证的厂商`boot.img`和Linux 6.12.69，只完成rootfs-only产物。
M1实机烧录启动验收已于2026-09-16完成（见6.7），完整`update.img`亦已于同日生成；
剩余收口项为以整镜像方式烧录该`update.img`并在板上复验`systemctl --failed`归零。
Windows交付目录：

```text
`stages/stage03-yocto-bsp/release-rootfs-m1-20260916/`
```

Stage3 M1实验室镜像的串口登录参数（明文）如下：

| 项目 | 值 |
|---|---|
| 串口设备 | `ttyFIQ0` |
| 串口参数 | `115200 8N1` |
| 登录账号 | `root` |
| 登录密码 | 空密码（不输入任何字符，直接按回车） |

镜像内`/etc/shadow`对应项为`root::20690:7:90:7:::`，并启用了
`serial-getty@ttyFIQ0.service`。该空密码只用于当前实验室烧录验证，不能用于正式交付镜像。

### 6.1 建议目录

```text
meta-tl3572/
├─ conf/
│  ├─ layer.conf
│  └─ machine/tl3572-evm.conf
├─ recipes-kernel/linux/
│  ├─ linux-tl3572_6.12.bb
│  └─ files/
│     ├─ tl3572_defconfig
│     ├─ mica.cfg
│     └─ tl3572-mica.dtsi
├─ recipes-bsp/
│  ├─ u-boot/
│  ├─ loader/
│  └─ firmware/
├─ recipes-mica/
│  ├─ mcs/
│  └─ uniproton/
├─ recipes-core/images/
│  └─ tl3572-openeuler-mcs-image.bb
└─ classes/
   └─ rockchip-update-image.bbclass
```

### 6.2 Machine配置

定义：

- `MACHINE = "tl3572-evm"`；
- AArch64 tune；
- 厂商内核provider；
- TL3572 DTB；
- ext4根文件系统；
- 内核模块和固件依赖；
- MCS/MICA feature；
- Rockchip镜像输出格式。

### 6.3 厂商内核配方

- 固定Linux 6.12.69源码包或提交；
- 固定defconfig；
- 添加MICA配置片段；
- 构建Image、DTB、模块和内核开发文件；
- 输出可用于编译 `mcs_km.ko` 的一致内核build目录。

### 6.4 Rockchip打包

首版允许调用厂商打包工具：

```text
Yocto rootfs.ext4
  + 厂商 boot.img
  + uboot.img
  + loader
  + parameter.txt
  → TL3572 update.img
```

MICA内核适配完成后，再由Yocto生成新版boot.img并替换厂商boot.img。

### 6.5 将中等及以上价值的诊断工具并入BSP镜像

阶段3创建`recipes-core/images/tl3572-openeuler-mcs-image.bb`时显式加入以下拆分包：

```bitbake
IMAGE_INSTALL:append = " util-linux-findmnt iproute2-ss glibc-external-utils "
```

对应关系和验收用途：

| 命令 | Yocto拆分包 | 阶段3用途 |
|---|---|---|
| `findmnt` | `util-linux-findmnt` | 核对rootfs、oem、userdata及后续RTOS固件分区的挂载源、类型和参数 |
| `ss` | `iproute2-ss` | 核对SSH、`micad`及其他TCP/UDP/Unix Socket的监听和连接状态 |
| `getent` | `glibc-external-utils` | 通过NSS核对用户、服务和DNS主机名解析，不再用`ping`代替DNS专项检查 |

阶段3镜像启动后执行：

```bash
command -v findmnt ss getent
findmnt -no SOURCE,FSTYPE,OPTIONS /
ss -lntup
getent hosts www.openeuler.org
```

这三项是阶段3可诊断性要求，不反向阻塞阶段2。`proc-fs-nfsd.mount`和`auditd.service`属于不使用服务的镜像清理问题，仍按阶段2收口项单独处理。

### 6.6 验收

- 干净工作区能够重建；
- 构建输出带版本清单和构建/验收日志；
- rootfs-only镜像可以生成并通过离线验收（`PASS`，2026-09-16，M1 实机烧录启动验收亦通过，见6.7）；
- 完整update.img可以生成（`PASS`，2026-09-16 M2 生成并三重回解验证；整镜像实机烧录复验待执行）；
- 不依赖手工复制未记录文件。
- `findmnt`、`ss`、`getent`均来自镜像配方且在实机可直接运行（`PASS`，2026-09-16 实机验证）。

预计：3～8天。

### 6.7 2026-09-16 M2：实机验收、nfs 清理与完整 update.img 生成

#### M1 镜像实机验收（通过）

M1 rootfs 经 RKDevTool 只烧 rootfs 分区（`0x0007a000`）后，串口（COM7/CH340，`ttyFIQ0 115200 8N1`）实测全部通过：

| 验收项 | 实测结果 | 状态 |
|---|---|---|
| 串口登录 | `root`/空密码登录成功，serial-getty@ttyFIQ0 正常 | `PASS` |
| 系统身份 | `openEuler Embedded 24.03-LTS`，hostname `tl3572-openeuler` | `PASS` |
| 厂商内核保留 | `6.12.69-gf1b67c293213` | `PASS` |
| 挂载 | `/`←`mmcblk0p6` ext4 rw；`/oem`←p7；`/userdata`←p8 | `PASS` |
| 网络 | eth0 DHCP `192.168.2.142/24`、默认路由、networkd/resolved active；Windows→板卡 TCP/22 通 | `PASS` |
| 诊断工具 | `findmnt`/`ss`/`getent` 全部可用；`getent hosts www.openeuler.org` 解析成功 | `PASS` |
| MICA 预置 | `mcsctl --help` 正常；`micad` disabled/inactive（预期） | `PASS` |
| 厂商模块 | `/lib/modules/*.ko` 共 7 个 | `PASS` |
| 失败单元 | 仅 `proc-fs-nfsd.mount`（已知项，本轮 M2 解决）；`sshd.service` 显示 inactive 为 socket 激活所致（`:22` 由 systemd 持有），非故障 | `PASS`（除已知项） |

串口日志归档：`stages/stage03-yocto-bsp/release-rootfs-m1-20260916/logs/serial-verify-stage3m1-20260916.txt`（117 行）。

#### nfs 清理（三条依赖路径全部封堵）

`NO_RECOMMENDATIONS=1` 无法阻止 nfs 系包进入镜像，因为全部是 `RDEPENDS` 硬依赖。在 `meta-tl3572-stage3` 新增三个 packagegroup bbappend：

| 路径 | 依赖 | 修复 |
|---|---|---|
| `packagegroup-network` | → `packagegroup-network-nfs` → `nfs-utils(-client)` | `RDEPENDS:${PN}:remove` |
| `packagegroup-base`（distro nfs 特性开启时） | → `packagegroup-base-nfs` → `rpcbind` | `RDEPENDS:packagegroup-base:remove` |
| `packagegroup-core-full-cmdline-sys-services` | → `nfs-utils` + `rpcbind`（镜像 feed 内 `dnf repoquery --whatrequires` 反查发现） | `RDEPENDS:...-sys-services:remove` |

同时在 `tl3572_bsp_rootfs_config` 中加入 `proc-fs-nfsd.mount -> /dev/null` mask 作兜底。第二轮重建 2845 任务全部成功，manifest 中 nfs/rpcbind 计数 **0**，rootfs 内 nfs systemd 单元数 **0**，e2fsck 五阶段 clean。

产物：`tl3572-openeuler-mcs-image-tl3572-evm-20260916034914.rootfs.ext4`（4 GiB，SHA256 `b767278c...de36c5f`）。修改前配方快照：构建机 `/home/openeuler/build/tl3572-2oo3/manifests/stage3-m2-pre-edit-20260916/`。

#### 完整 update.img 生成（Rockchip 打包）

交付目录：`stages/stage03-yocto-bsp/release-update-m2-20260916/`

- `update-tl3572-openeuler-stage3-m2.img`（4,119,118,524 字节，SHA256 `03400abf...c36b46`）：厂商 Loader/GPT/U-Boot/Trust/boot(6.12.69)/recovery/oem/userdata 全部原封 + openEuler rootfs
- rootfs 缩容至 3,999,997,952 字节（SHA256 `2afc6c96...2dc05e8`，e2fsck clean）：RKFW 头 `fw_size` 为 u32，4 GiB rootfs 会令 firmware 总长（4,413,261,828）溢出 4,294,967,295，`RKImageMaker` 报 "Get image version failed"。板上 rootfs 分区 14 GiB，缩容无影响
- 组装方法：`AFPTool -unpack` 拆厂商 `firmware.img` 得 10 个分区镜像 → 换入新 `rootfs.img` → `AFPTool -pack` 重组 firmware → RKFW 层手工组装（厂商头仅 `0x25` 处 `fw_size` 3 字节差异，boot 区原样）+ 32 字节整文件 MD5。RKImageMaker v2.23 无法解析 AFPTool v2.28 重组的 firmware（实测拒绝原尺寸重组件），故绕过该工具
- 三重验证通过：①`RKImageMaker -unpack` 接受并回解，boot.bin/firmware SHA 一致；②`AFPTool -unpack` 回解，rootfs SHA 精确匹配、其余 9 个分区文件与厂商逐字节一致；③头部审计：与厂商镜像仅 `fw_size` 字段 3 字节差异，os_type/日期等全部保持厂商原值
- 另归档：rootfs gz（93 MB）、manifest、e2fsck（原始 4 GiB 与缩容版）、构建日志、`SHA256SUMS`、`烧录说明.txt`、`pack\` 分区素材

#### 阶段3剩余收口项

1. ~~以整镜像方式烧录 `update-tl3572-openeuler-stage3-m2.img`（RKDevTool 升级固件，Loader 模式），串口确认 `systemctl --failed` 为 0 个单元~~ **`PASS`，2026-09-16**：整镜像烧录后串口实测 `systemctl --failed` 返回 **"0 loaded units listed."**；`pgrep rpcbind`/`rpc.statd` 空、`/proc/mounts` 无 nfsd；厂商内核 `6.12.69-gf1b67c293213` 保留；`/`←`mmcblk0p6`（3.5G 可用，缩容后预期值）、`/oem`←p7、`/userdata`←p8；eth0 DHCP `192.168.2.143`、networkd active、Windows→板卡 TCP/22 通；`findmnt`/`ss`/`getent`/`mcsctl` 可用；7 个厂商模块；`getent hosts` 解析正常；`micad` disabled/inactive（预期）。日志：`stages/stage03-yocto-bsp/release-update-m2-20260916/logs/serial-verify-stage3m2-20260916.txt`（77 行）。
   已知无害差异：整镜像烧录后 `/oem`（7.3M 可用）与 `/userdata`（3.5M 可用）文件系统为厂商 update.img 内自带小镜像的原生大小（工厂首次烧录的 124M/15G 文件系统更大）；userdata 分区本身仍为 grow 全容量，板上可按需 `resize2fs /dev/mmcblk0p8` 扩容。
2. 冷启动 10 次与 24 小时运行：经决策延后，与阶段 4 验证合并执行（阶段 2 遗留项同步顺延）。
3. 阶段 3 标记 `COMPLETE`（2026-09-16），下一阶段：阶段 4（Linux 6.12 MICA/MCS 内核适配）。

## 7. 阶段4：Linux 6.12 MICA/MCS适配

阶段状态：`COMPLETE`（2026-09-17）。M4a 摸底、M4b 新内核 boot.img（v3 起实机启动）、M4c mcs_km 适配（of-cpu 版实机加载）、M4d DTB 保留内存与 CPU 预留（maxcpus=7，v4 实机验证）已全部通过；Yocto 正式化（`linux-tl3572_6.12.bb` + mcs_km 入 rootfs + 完整 update.img）已完成并通过三重回解验证及整镜像实机复验（见 7.8）。M4e 的模块压测与稳定性测试保留为阶段 4 待办，后续查缺补漏时执行，不阻塞阶段 4 结项。实测记录见 7.7/7.8。

### 7.1 内核配置

至少启用：

```text
CONFIG_REMOTEPROC=y
CONFIG_RPMSG=y
CONFIG_RPMSG_NS=y
CONFIG_RPMSG_VIRTIO=y
CONFIG_RPMSG_CHAR=y
CONFIG_RPMSG_CTRL=y
CONFIG_VIRTIO=y
CONFIG_HOTPLUG_CPU=y
CONFIG_OF_RESERVED_MEM=y
CONFIG_ARM_PSCI_FW=y
CONFIG_RPMSG_ROCKCHIP_MBOX=y
```

### 7.2 将mcs_km适配到6.12

逐项处理：

- remoteproc API变化；
- RTOS ELF加载；
- `.resource_table`解析；
- `rproc_ops`；
- CPU start/stop；
- `da_to_va`；
- vring和RPMsg初始化；
- SGI/IPI路由；
- 实例资源回收；
- 异常启动回滚；
- 模块卸载和重复加载；
- 多实例数据结构不能使用单例全局地址。

优先对比远端已有RK3588 UniProton/MICA适配，但所有差异都必须重新核对RK3572 CPU、GIC、内存和PSCI。

### 7.3 内存规划

M5 已实测可用的 MCS 总保留区为 `0x7a000000～0x7dffffff`，共 64 MiB。
M6/M7 不再按“每实例 64 MiB”扩张，而是在该区域内固定切片，避免继续侵占 Linux
内存。下表已按 M6 实测布局定案；M5 的 CPU7 单实例地址仅作为历史基线：

| 区域 | 地址 | 大小 | 用途 |
|---|---|---:|---|
| 主控共享区 | `0x7a000000～0x7affffff` | 16 MiB | MCS/OpenAMP、独立 vring、2oo3 状态和保护间隔 |
| UniProton A | `0x7b000000～0x7bffffff` | 16 MiB | A 的日志、ELF、heap/stack、MMU 表 |
| UniProton B | `0x7c000000～0x7cffffff` | 16 MiB | B 的日志、ELF、heap/stack、MMU 表 |
| UniProton C | `0x7d000000～0x7dffffff` | 16 MiB | C 的日志、ELF、heap/stack、MMU 表 |

主控共享区按逻辑 CPU ID 分配 128 KiB OpenAMP 槽位，公式为
`0x7a000000 + cpu_id * 0x20000`。M6 已实测 CPU4/CPU5 分别使用
`0x7a080000～0x7a09ffff` 和 `0x7a0a0000～0x7a0bffff`；M7 把 UP-A 移到 CPU3 后，
第三个活动槽位为 `0x7a060000～0x7a07ffff`。规划中的 2oo3 共享状态区继续保留
`0x7a300000～0x7aafffff`，不会与这些 OpenAMP 槽位重叠。
每个 16 MiB 实例切片沿用 M5 已验证的比例：2 MiB 日志、8 MiB 镜像与运行区、
6 MiB MMU/保护区。M6 已验证 A/B 的 vring 与物理映射分别落在对应共享池；M7
新增 C 时必须对第三个窗口重复边界检查。

地址以完整 DTS 和 `/proc/iomem` 为最终依据，不能复制 QEMU、树莓派、RK3568 或
RK3588 的物理地址，并继续避开 TF-A、OP-TEE、GPU/NPU、DRM、CMA、ramoops 和
其他固件保留区。

### 7.4 CPU分配演进

RK3572 拓扑为 CPU0～3=A53 cluster0、CPU4～5=A53 cluster1、CPU6～7=A73
cluster2。修订后的默认方案优先把实时负载放在 A53，并把两颗 A73 留给 Linux：

| 里程碑 | Linux | UniProton | 说明 |
|---|---|---|---|
| M5 打通基线（已完成） | CPU0～6 | CPU7（A73） | 仅保留历史实测基线 |
| 单实例优化基线（已完成） | CPU0～4、CPU6～7 | CPU5（A53，MPIDR `0x101`） | M6 前置已于 2026-09-21 通过 |
| M6 双实例（已完成） | CPU0～3、CPU6～7 | CPU4、CPU5（A53） | 两颗 A73 均归 Linux；正反序与隔离通过 |
| M7 三实例默认方案 | CPU0～2、CPU6～7 | CPU3、CPU4、CPU5（A53） | 三个副本同核型 |
| 2oo3 跨 cluster 可选方案 | CPU0～2、CPU4、CPU6 | CPU3、CPU5、CPU7 | 牺牲一颗 A73，换三个 cluster |

M5 的 `maxcpus=7` 已通过 `CONFIG_CMDLINE_FORCE` 固化并完成实机验证，但 CPU7
选择只是为了用连续编号快速打通，不是量产资源定案。2026-09-21 已用新的
`mcs_reserve_cpus=5` 机制把单实例迁移到 CPU5，并完整重跑冷启动、SGI8、RPMsg、
10,000 次 451B 大包和 1,000 次生命周期回归。M6 随后扩展为
`mcs_reserve_cpus=4-5`，完成 SGI8/SGI9 双实例闭环；两个阶段中 CPU6/CPU7 均由
Linux 正常上线。

后续不得把固化串简单改为 `maxcpus=3/4/5`：该参数只能保留连续前缀 CPU，无法在
保留 CPU4/5 的同时重新启用 CPU6/7。必须在 Linux SMP 启动前实现按逻辑 CPU/MPIDR
精确保留，并确认 `/sys/devices/system/cpu/online` 与目标掩码一致；仅在用户态把 CPU
热下线不作为正式方案。厂商 U-Boot 为 `ENV_IS_NOWHERE`，因此最终启动参数或 CPU
保留策略仍需通过内核配置、DT 或受控内核补丁进入 Yocto 构建。

#### 7.4.1 外设所有权建议（M7～M9默认方案）

M6 当前只完成 CPU、内存、SGI 和 OpenAMP 的隔离，**尚未把任何板级物理外设直通给
UP-A/UP-B**；现有外设仍由 Linux 驱动。这不是遗漏，而是 2oo3 架构的推荐起点：
Linux 侧输入代理对物理输入只采集一次，生成带 `epoch/cycle_id/timestamp/CRC` 的不可变
快照，再向三个 UniProton 广播；三个实例只返回输出提案，表决后由唯一 I/O 代理写入
物理设备。这样可保证三个副本接收同一输入，并避免寄存器、时钟、复位、pinmux、IRQ
或 DMA 被多个 OS 同时控制。

板上外设的建议归属如下；CAN/串口的逻辑用途可在现场协议清单确定后调整，但硬件所有者
必须保持唯一：

| 类别 | TL3572-EVM接口 | 建议所有者 | 默认用途与约束 |
|---|---|---|---|
| 启动、存储与恢复 | eMMC/UFS、Micro SD、USB、PCIe/NVMe | Linux | 系统启动、升级、日志与恢复；不直通 RTOS |
| 管理网络 | `eth0`（千兆网口） | Linux 网络栈 | SSH、升级、诊断和非实时业务 |
| 实时现场网络 | `eth1`（千兆网口） | Linux 唯一 I/O 代理 | 预留 EtherCAT/实时以太网；与管理流量隔离，三个 RTOS 不直接打开网卡 |
| 维护备用网络 | USB 百兆网口 | Linux | 维护或故障转移；USB 调度抖动较大，不作为硬实时 EtherCAT 主链路 |
| CAN FD | `can0`～`can3` | Linux 输入代理/I/O 代理 | 建议 `can0/1` 作双路现场输入，`can2` 作辅助设备，`can3` 作诊断、输出或故障注入预留；发送动作只由 I/O 代理执行 |
| RS-485 | UART1、UART2 | Linux 输入代理/I/O 代理 | 建议作为 Modbus RTU A/B 通道；轮询、时间戳和写操作集中管理 |
| RS-232 | UART4、UART8 | Linux | 维护台或遗留仪表；不与 Linux 控制台复用 |
| 调试串口 | UART0/`ttyFIQ0` | Linux | 启动日志和救援入口；UniProton 日志走 RPMsg，避免争抢串口 |
| 离散量输入 | DI1～DI4（GPIO531、532、533、434） | Linux 输入代理 | 单次采样、去抖、统一时间戳后广播给三个实例 |
| 模拟量输入 | 6 路 ADC | Linux 输入代理 | ADC 控制器不可按通道跨 OS 拆分；统一采样并广播快照 |
| 物理输出 | DO1～DO4（GPIO539～542）、PWM、CAN TX、Modbus 写、EtherCAT PDO | Linux 唯一表决/I/O 代理 | 三个 RTOS 只提交提案，任何现场输出只能有一个写入者 |
| 板级管理 | I2C0/1/5/6/10、RTC、风扇、PLP、电源/复位 GPIO | Linux | 同一 I2C 控制器/总线不跨 OS 拆分；保留完整系统管理能力 |
| 多媒体/加速 | MIPI CSI/DSI、HDMI、音频、GPU/NPU | Linux | 不进入控制闭环，避免占用 RTOS BSP 与中断预算 |
| 扩展接口 | DSMC16、SPI4、扩展 GPIO | 暂不分配 | 优先预留给后续 FPGA/CPLD/安全 MCU 或产品扩展，不作普通应用占用 |
| RTOS 本地资源 | 私有 RAM/MMU 区、每核定时器、独立 SGI、各自 OpenAMP 槽位 | UP-A/UP-B/UP-C 各自独占 | RTOS 默认不拥有板级物理外设，仅运行确定性算法和健康监测 |
| 外部看门狗 | 板载独立 watchdog | Linux supervisor 暂管，量产可迁移至安全岛 | 仅在输入代理、表决器和必需 RTOS 心跳均健康时喂狗；任何单个 RTOS 不得独自喂狗 |

如果后续必须验证“RTOS 直接采集”模式，可把三个独立 CAN 控制器分别独占分配给
UP-A/UP-B/UP-C（建议 `can0/can1/can2`），Linux 保留 `can3`；前提是三个物理 CAN
通道能提供语义和周期一致的冗余输入，且 UniProton 已补齐对应控制器、时钟、复位、
pinctrl、IRQ 和 DMA 驱动。该模式下必须在 Linux DT 中禁用被直通的完整控制器节点，
不能只拆分某几个 CAN ID。ADC、I2C、单个 GPIO bank 等共享寄存器控制器不采用跨 OS
拆分；若需要更强故障隔离，应增加外部 ADC、FPGA/CPLD 或安全 MCU，而不是让多个 OS
并发访问同一控制器。

M7 延续上述默认方案：新增 UP-C 只获得 CPU3、第三实例内存、SGI10 和 OpenAMP 槽位，
不新增物理外设直通。M8 再实现输入代理与三路快照广播，M9 接入唯一表决/I/O 代理和
外部输出使能/看门狗闭锁。

### 7.5 DTB修改

- 创建每个RTOS独占的reserved-memory；
- 创建每个实例的通信/vring区域；
- 创建MCS remoteproc实例节点；
- 标记Linux不能映射或分配的区域；
- 校验地址、长度、对齐和phandle；
- 每个物理控制器的寄存器、时钟、复位、pinmux、IRQ 和 DMA 只允许一个 OS 所有；
- 默认不向 M7 的三个 RTOS 直通板级外设；若启用可选直通方案，必须在 Linux DT 中禁用完整控制器节点；
- UART0 调试串口、eMMC/UFS 和恢复通道始终保留给 Linux。

### 7.6 Linux侧验收

1. 新boot.img可启动；
2. 保留内存不进入Linux页分配器；
3. Linux只在线预定CPU；
4. `mcs_km.ko`可加载；
5. `micad`可启动；
6. `mica status`可用；
7. RTOS加载失败不影响Linux；
8. 模块反复加载/卸载1000次无泄漏和崩溃。

预计：4～10天。

### 7.7 2026-09-16 阶段4实测记录（M4a～M4d）

详细过程与产物哈希见 `stages/stage04-mica-mcs/worklog-20260916/`（`docs/`、
`artifacts/实机验证结果-20260916.txt`）。

#### M4a 摸底（完成）

- 内核源码=厂商 `linux-6.12.69-v1.0-gf1b67c2.tar.gz`（SHA256 与阶段1清单一致）；工具链=Arm GNU aarch64-none-linux-gnu-gcc 14.3.1（厂商同款，不能用 openEuler gcc 12.3）；
- `.config` 以板上 `/proc/config.gz` 原样种子 + `scripts/config -e REMOTEPROC RPMSG_CHAR RPMSG_CTRL`；
- 版本号以源码根 `localversion`（`-gf1b67c293213`）复现，utsrelease 与厂商逐字符一致，板上 7 个厂商模块 vermagic 兼容；
- IPI 通道：`arch/arm64/kernel/smp.c` 追加补丁预留 SGI8 给 mcs_km（`arm64_mcs_ipi_virq()`/`arm64_mcs_ipi_send()`，EXPORT_SYMBOL_GPL），0001 号补丁。

#### M4b 新内核 boot.img（实机启动通过，v3）

boot.img 打包共四轮迭代，教训固化为规则：

| 版本 | 改动 | 结果 |
|---|---|---|
| v0 | 源码树自带 boot.its 去签名节点，embedded-data FIT | U-Boot `No valid android hdr` / `No fit blob`，拒启 |
| v1 | 改 Rockchip 外置数据 FIT：`mkimage -B 0x200 -E -p 0x800`（头 0x600、首数据偏移 0x800） | 过 hdr 校验，但 U-Boot 在 `ufs@29e00000` 自动探测 Data Abort |
| v2 | 不再整编 DTB（自编 DTB 约 800 个 phandle 重编号），改厂商原 DTB + overlay 只追加 mcs-rmem/mcs-remoteproc（UFS phandle 保持 0x44f） | UFS abort 仍在 |
| v3 | v2 + 将本板未使用的 `/soc/ufs@29e00000` 置 `disabled` | **实机启动成功**，Linux 到登录界面 |

v3 实机验证（2026-09-16 16:59）：新内核 `#2 SMP Sep 16 13:48:38 CST 2026` 在板上运行、rootfs（mmcblk0p6）正常读写挂载、eth0 192.168.2.143、`systemctl --failed`=0、`/proc/iomem` 出现 `134000000-137ffffff : reserved`、mcs-remoteproc 节点在位。产物归档：`tl3572-stage4-external-fit-v3-20260916\`。

#### M4c mcs_km 适配（实机加载通过）

- 原版模块首载失败：板上内核未启用 `CONFIG_KPROBES`，`register_kprobe("cpu_logical_map")` 返回 -95；
- 修复（0003 号补丁）：弃 kprobe，改用内核已导出的 `of_get_cpu_node()` + DT CPU `reg` 属性（本板 CPU 节点 #address-cells=1、reg 为 u32）取 MPIDR；
- `mcs_km-tl3572-of-cpu.ko`（SHA256 `1c42336c...aadb`，vermagic `6.12.69-gf1b67c293213 SMP mod_unload aarch64`）在 v3 与 v4 内核上 insmod/rmmod 均干净通过，`/dev/mcs`（508:0）创建/清理正常，无 oops。

#### M4d DTB 保留内存 + CPU 预留（实机验证通过，v4）

- 保留内存：`mcs-rmem@134000000` 64 MiB（16M SHM + 36M 实例 + 余量），dts 补丁 0002；实机 /proc/iomem 与 dmesg 均确认该段不再属于 System RAM；
- CPU 预留：U-Boot env 路线实测不可行（`Loading Environment from nowhere`；`Hit key to stop autoboot('CTRL+C'): 0`——env 不落盘、自启只认 CTRL+C 且零倒计时，CR 无法打断）；改 v4 内核 `CONFIG_CMDLINE_FORCE` 固化厂商 cmdline + `maxcpus=7`；
- v4 烧录走板上 Linux 直写 `/dev/mmcblk0p3`（boot 分区 64 MiB，即 RKDevTool 地址 0x0000a000；分区表 p1=uboot p2=misc p3=boot p4=recovery p5=backup），三重防护（镜像 SHA / p3 FIT 魔数 / p3 尺寸）+ 烧前备份（板上 `/root/boot-p3-backup-pre-v4.img`）+ 回读 SHA 校验；
- v4 实机验证（17:40）：`/proc/cmdline` 为固化完整串含 `maxcpus=7`；nproc=7；online `0-6`、offline `7`、present `0-7`（CPU7 从未进入 Linux，可经 PSCI 拉起，衔接阶段5）；`smp: Brought up 1 node, 7 CPUs`、`SMP: Total of 7 processors activated`，dmesg 中 CPU7 出现 0 次；`systemctl --failed`=0；mcs 保留内存与 remoteproc 节点完好；v4 上 mcs_km 加载与 micad/mcsctl 复验通过；
- v4 产物：`tl3572-stage4-external-fit-v4-maxcpus-20260916\`（boot.img 40,647,168 字节，SHA256 `5bdd356b...158691`；gz 副本 SHA `44ec6de0...8212`）。

#### 板上补验（17:14–17:42）

- `CONFIG_REMOTEPROC=y` / `RPMSG_CHAR=y` / `RPMSG_CTRL=y` 在板上运行内核确认（厂商内核此三项为 not set，证明新内核生效）；
- `systemctl start micad` → active (running)；`mcsctl status` RC=0，返回 `uniproton`/`uniproton-gdb` 两实例 Offline——无 RTOS 固件属预期；注意厂商默认实例配置指向 rpi4 固件路径与 CPU 3，阶段5 需替换为 TL3572 实例配置（CPU7 + 真实固件路径）。

#### 阶段 4 保留待办（M4e，不阻塞结项）

1. 10 次冒烟 + 1000 次模块加载/卸载压测（用户决策顺延至以后查缺补漏）；
2. 冷启动 10 次 + 24 小时稳定性（此前已顺延，与本项合并执行）；
3. ~~内核成果 Yocto 化~~ **完成（2026-09-16），见 7.8**。

阶段 4 已于 2026-09-17 标记为 `COMPLETE`；上述 1～2 项继续登记在阶段 4 下，作为非阻塞保留测试，不影响进入阶段 5。

### 7.8 2026-09-16 Yocto 正式化（M4 收官）

#### linux-tl3572 配方（meta-tl3572-stage3）

- `recipes-kernel/linux/linux-tl3572_6.12.69.bb` + `files/` 十件套：厂商源码 tarball（重打包加顶层目录，原始 SHA256 与阶段1清单一致）、**0001 完整补丁**（从纯净树全量 diff 重新生成，含此前保存版遗漏的 `arch/arm64/include/asm/smp.h` 声明）、v4 defconfig、localversion、vendor-boot.img（供配方内 dumpimage 提取 fdt/resource）、mcs overlay dts（fdtoverlay 应用）、外置 FIT its、mcs_km.c（of-cpu 版）+ Makefile、0003 适配记录补丁；
- 设计：刻意**不作为 virtual/kernel provider**（机器配置仍 `linux-dummy`，不破坏 stage3 已验证的 rootfs 流）；工具链显式注入厂商同款 Arm GNU 14.3.1（不用 Yocto 外部 gcc 12.3）；产物 = boot.img 部署件 + mcs_km.ko 包（`IMAGE_INSTALL` 进镜像，/lib/modules 厂商扁平布局）；
- do_compile 内置硬断言：utsrelease 精确匹配、模块 vermagic 固定串直查、vendor.dtb/resource/fdt 三个 SHA256（fdt 断言与板上验证版逐字节一致 `195535eb...`）、FIT 内 fdt/resource 哈希；
- 构建三轮踩坑（已修复并记录）：① `file://...;subdir=mcs-km` 的模块 Makefile 必须名为 `Makefile`；② 二进制里查 vermagic 用 `grep -aq` 固定串（`[^ ]*` 正则会吞 NUL 后整段 .modinfo，且 bash 命令替换静默丢 NUL 造成"看起来相等实不相等"）；③ 修改远端文件一律走本地文件→`tr -d '\r'`→管道的无损路径，内联 heredoc 会吃反斜杠；
- 结果：2920 个 bitbake 任务全绿；manifest 含 `linux-tl3572 tl3572_evm 6.12.69`，nfs/rpcbind 计数 0；rootfs `/lib/modules/` 共 8 个 .ko（7 厂商 + mcs_km）；boot.img FIT 内 fdt 哈希与验证版一致。

#### 完整 update.img 交付

- `stages/stage04-mica-mcs/release-update-20260916/update-tl3572-openeuler-stage4.img`（4,119,186,108 字节，SHA256 `6eafe110...860ecf`；同目录含烧录说明、SHA256SUMS、pack/ 素材、内核 Image/mcs_km.ko/config/manifest 归档）；
- rootfs 缩容 4,294,967,296 → 3,999,997,952 字节（resize2fs + e2fsck 前后双检，RKFW fw_size u32 限制），SHA256 `5cdd9cc5...eefa2`；
- RKFW 组装脚本先经自检：以厂商 firmware 段重组厂商镜像，输出与厂商原件 SHA256 逐字节一致（`c66ffb62...`）方投入使用；
- 三重回解验证通过：①RKImageMaker -unpack 接受并回解，导出 firmware.img 与原件 SHA 一致（`99569d34...`），导出 boot.bin = 厂商镜像 boot 区 = MiniLoaderAll.bin（`bd3c4eab...`）；②AFPTool -unpack firmware.img 回解，10 个分区与 pack 输入逐字节一致；③头部 python 逐字节 diff，与厂商镜像仅 fw_size 字段 3 字节差异。AFPTool -unpack 直接作用于重组 update.img 报 check crc failed 属该工具对重组 RKFW 的固有行为（对 stage3 已实机烧录验证的镜像同样报错），验证需经 RKImageMaker 拆外层；
- 本整镜像已于 2026-09-16 19:2x **整镜像烧录并实机复验通过**：RKDevTool 升级固件（镜像已从 USB 外接盘复制到本地盘，避开 USB 读写冲突；首次烧录工具中途退出，重进 Loader 模式 + 管理员运行后成功）。板上实测：`6.12.69-gf1b67c293213 #1 SMP`（Yocto 产物）、cmdline 固化串含 maxcpus=7、nproc=7 / online 0-6 / offline 7 / present 0-7、`systemctl --failed`=0、/lib/modules 8 个 .ko（含 mcs_km.ko）、`/proc/iomem` mcs-rmem reserved、/←p6 /oem←p7 /userdata←p8、eth0 DHCP、insmod mcs_km→/dev/mcs 508:0→rmmod 干净、micad active + mcsctl status 两实例 Offline（预期）。注意：整镜像烧录使板上 rootfs 全新（/root 实验文件与 p3 备份已不存在；SSH 主机密钥为全新生成，ed25519 指纹 `SHA256:jJ6U1DCL10dLFgJTTVR1ZWOFDEGsQb27JJnzvwrKAVM`；DHCP 地址本轮为 192.168.2.144，动态可能变化）。

## 8. 阶段5：单UniProton移植

阶段状态：`COMPLETE`（2026-09-18，当前功能与构建范围）。M5.1 骨架、M5.2
构建和 M5.3 单实例闭环均已通过；最终 ELF 的 10,000 次 451B 回显、1,000 次
stop/start+回显、最终 Yocto boot.img 冷启动及 AutoBoot 均为 `PASS`。72 小时稳态
与 panic/死循环/非法访问故障注入按本次收尾决定列为非阻塞延期补测，未执行项不写
成已通过，也不阻塞进入阶段6。CPU7/A73 分配只作为 M5 打通基线保留；按逻辑
CPU/MPIDR 精确保留和 CPU5/A53 单实例迁移已在 2026-09-21 完成，不重新打开 M5
结论，详细证据见 `stages/stage06-multi-uniproton/docs/m6-pre-cpu5-migration.md`。

### 8.1 建立RK3572板级目录

```text
UniProton/demos/rk3572_mica/
├─ config/
├─ bsp/
│  ├─ start.S
│  ├─ exception.S
│  ├─ hwi_init.c
│  ├─ timer.c
│  ├─ mmu.c
│  └─ cache.S
├─ openamp/
├─ resource_table/
├─ linker/rk3572.ld
├─ apps/rpmsg_echo/
└─ build/
```

### 8.2 最小BSP适配

- ARMv8启动入口；
- 栈、BSS和异常向量；
- MPIDR到逻辑CPU映射；
- GICv2（GIC-400）；
- Generic Timer；
- MMU和页表；
- Cache属性和内存屏障；
- PSCI启动参数；
- 中断开关；
- 日志先走RPMsg或独立共享日志区。

### 8.3 链接与资源表

- 所有段位于本实例独占内存；
- ELF入口正确；
- `.resource_table`位于ELF可解析段；
- 代码、数据、BSS、heap、stack、vring不重叠；
- 不访问Linux或其他实例内存；
- 固件带实例版本、构建提交和CRC。

### 8.4 OpenAMP/RPMsg

- 建立virtio device；
- 初始化TX/RX vring；
- 分配唯一notify ID；
- 实现IPI收发；
- 注册唯一RPMsg endpoint；
- 正确处理cache flush/invalidate；
- 加入序号、长度和CRC检查。

### 8.5 单实例验证顺序

1. MICA解析并加载ELF；
2. CPU7进入UniProton入口；
3. 定时器中断工作；
4. RPMsg service出现；
5. Linux→UniProton ping；
6. UniProton→Linux echo；
7. 大包和长时间压力；
8. 停止并重新启动；
9. panic、死循环、非法访问故障注入；
10. 连续运行72小时。

退出条件：单实例可以稳定启停，Linux不需要重启即可恢复通信。

预计：1～3周。

### 8.6 2026-09-17 M5.1 骨架落地记录

- 源码起点确认：`tl3572-2oo3/src/UniProton` = git `1d102888`（与 rpi4 实机验证 ELF 同版本）；demos 无 rk3572，选定 demos/rk3588 为派生基线（Rockchip + GICv3 + MICA 最贴近）。resource_table 实际位于 `apps/openamp/rpmsg_backend.c`（非独立目录）；CMake 依赖树内 `build/uniproton_config/config_armv8_<board>` defconfig。
- 交付：`demos/rk3572_mica/` 整树（rk3588 派生，readme.txt 含状态与 M5.2 待办清单）；`build/rk3572_mica.ld` 基址改 **IMU_SRAM 0x1_34000000/8MiB + MMU_MEM 0x1_34800000/8MiB**（= mcs-rmem@134000000 64MiB no-map，0x1_35000000 起留 vring/日志区）；`config_armv8_rk3572` defconfig 复制就位；`build_app.sh` 改 ALL=rk3572_mica、工具链指 toolchain-14.3（Arm GNU 14.3.rel1，与内核同款；demo 原配 aarch64-none-elf 10.3，nosys.specs 打通属 M5.2 验证点）。
- micad 实例：`tl3572-2oo3/mica-deploy/tl3572-up0.conf`（CPU=7、AutoBoot=no、ClientPath=/lib/firmware/rk3572-uniproton.elf）+ 部署/回滚说明；rpi4 样板格式为 `[Mica] Name/CPU/ClientPath/AutoBoot` 四项。
- 有意保留：bsp/hal/ 仍为 RK3588 SDK 移植件（hal_cru_rk3588.c 等）——最小 BSP 路径不依赖 Rockchip HAL（日志走 RPMsg、时钟用 Generic Timer），需 UART/CRU 时再引 RK3572 对应件。
- M5.2 关键点：GICv3 基址（RK3572 手册）、MPIDR→CPU7（A53 cluster，预期 Aff0=3/Aff1=1 待核实）、SGI 对齐内核预留 nr_ipi=8、PSCI/secondary-entry 拉起约定、toolchain-14.3 构建打通 + ELF 入口断言 0x1_34000000。
- M5.1 历史过程结论已合并到本节与 M5.3 最终收口报告，不再保留独立过程文件。

### 8.7 2026-09-17 M5.2 构建打通记录

- **硬件参数定案**（厂商 rk3572.dtsi/tl3572-evm.dts + 实机 MIDR）：中断控制器为 **arm,gic-400（GICv2）**，GICD 0x2a601000/GICC 0x2a602000——M5.1 初始的"GICv3"规划有误；CPU 拓扑 3 簇 8 核（cluster0×4 A53 MPIDR 0x000-003、cluster1×2 A53 0x100-101、cluster2×2 A73 MPIDR 0x200-201），**CPU7=cpu_b1 MPIDR 0x201（A73）**；实机 CPU6/7 MIDR 为 `0x411fd090`，Linux `cputype.h` 将 part `0xd09` 定义为 Cortex-A73；armv8-timer PPI 13/14/11/10（频率运行时读 CNTFRQ_EL0）；PSCI 1.0 smc；调试串口 uart0@0x2c130000（earlycon 实证）。
- **基线切换**：GICv2 + micad 全链验证两大证据 → bsp/apps/config/根 CMakeLists 由 rk3588 结构**整套切到 raspi4 结构**（rk3588 原件在 demos/rk3588）；RPMsg 后端用 OS 树 src/component/mica（main.c 只是壳），vring 由 Master 分配。
- **适配要点**：cpu_config.h 重写（GICv2 宏集+RK3572 地址，MMU_IMAGE 0x134000000/MMU_OPENAMP 0x135000000/OPENAMP_SHM_SIZE 0x30000）；**VDEV 区由"镜像下方"改"镜像上方"**（旧公式会落 mcs-rmem 外的 Linux 内存）；notify **SGI 7→8**（对齐内核预留 nr_ipi=8）；链接 0x134000000/0x134800000。
- **构建注册链**（raspi4 派生）：globle.py cpus_/cpu_plat 加 rk3572、config.xml project（工具链 toolchain-14.3、cmake 改 /usr/bin）、uniproton_tool_chain.cmake arm64 白名单加 rk3572（不加则 cmake 静默回退 /usr/bin/cc）、新增 rk3572_armv8.cmake(.in)、defconfig config_armv8_rk3572（raspi4 基：GIC_VER=2、OPENAMP=y；POWEROFF 关）。
- **工具链适配**：toolchain-14.3 bin/ 建 aarch64-none-elf-* → aarch64-none-linux-gnu-* 软链（9 件）；lib/gcc/.../14.3.1/ 放 0 字节 nosys.specs（demo flags 写死 -specs=nosys.specs）。
- **gcc14 新默认 error 修复**（gcc10 下仅警告）：main.c/timer.c/rpmsg_backend_rsc_table.c 补 extern（TestClkStart/OsHwiInit/OsConfigStart/IsrRegister/OsHwiMcTrigger）；stackAddr 加 (uintptr_t)。**上游修复**：msgget.c msgid→uintptr_t、metal_io_init physmap const 转换、IsrRegister 调用 3 参→2 参（raspi4 树内版本漂移，原构建靠 gcc10 容忍）。
- **产物**：rk3572_mica.elf（587,512B，SHA256 2ab311e2...3a2eea）——入口 **0x1_340000000** 断言过、单 LOAD 段 MemSz 0xd2ab0（≪8MiB）、.resource_table@0x13404dbd0（0xa64）；已部署 mica-deploy/rk3572-uniproton.elf。MMU 四区：OPENAMP(DEVICE 0x30000)/IMAGE(CACHE 16MiB)/GIC(DEVICE 16MiB)/UART(DEVICE 4K)。
- 源码改动已合并到最终源码覆盖包；M5.2 过程结论保留在本节与 M5.3 最终收口报告，
  不再保留独立过程文件。
- **当时的 M5.3 进入条件（已于 8.9 完成）**：conf+elf 上板、mcsctl create/start up0、串口观察启动；运行时验证 start.S 入口约定/GICv2/SGI8/timer/RPMsg service。defconfig OS_CPU_TYPE 暂用 OS_RASPI4 枚举（语义正确，可选自定义）。

### 8.8 2026-09-17 M5.3 实机调试历史断点（已被 8.9 取代）

- **已打通**：rmem 迁移 0x134000000→**0x7a000000**（fdtput 改 fdt reg + mkimage 重打 FIT + 板内 dd p3，读回校验过；动机：openEuler micad 32 位 vring 分配 bug，>4GiB 基址被截断成 0x340e0000 落 Linux 内存被 mcs_km 正确拒绝）；`mcsctl start up0 successfully`（micad "start done"、Service=rpmsg-rpc rpmsg-umt）；PSCI 拉起 CPU7（MPIDR 0x201，串口见 OP-TEE I/TC 日志）；裸机跑到 OsStart 内。
- **实测裁决（X1，三轮复现）**：`vctl=0x5`（CNTV enable+pending）+ `ispendr0=0x8000200` → **CNTV 的 GIC 线是 hwirq 27（PPI11）非 30**（TEST_CLK_INT 已改 27）；**Linux 实发 SGI 9 非 8**（ispendr bit9；OS_HWI_IPI_NO_08→09 已改）。两改后 tick 仍不进。
- **当前卡点**：v9 X2 实验（`MSR DAIFCLR,#0x3` 解锁）打印后执行流立即跑飞（X3 不出现）→ pending 中断一进就死 → **异常向量/VBAR 问题**。线索：内核侧 prt_reset_vector.S 有 OsVectTblInit 设 VBAR_EL1=OsVectorTable，但 demo 的 raspi4 版 start.S 疑似未走该路径；且链接脚本无 vectors 段/ALIGN(2048)，arm64 VBAR 要求 2KB 对齐——**高嫌疑：向量表未安装或未对齐**。
- **下一步**：①读 demo start.S + prt_reset_vector.S 确认 OsVectTblInit 调用链；②readelf 查 OsVectorTable 对齐；③v10 读 VBAR_EL1 实测；④tick 通后预期链 E→F→rpmsg init→IPI 计数→echo（回显模板已在 rpmsg_service.c:150）。
- **历史断点说明**：本节已合并原调试交接中的验证流程、v3～v9 结论和关键坑点；
  对应中间 ELF、boot、串口日志及临时交接文件不再作为复现输入保留。

### 8.9 2026-09-18 M5.3 单实例功能闭环

- **最终内存布局**：mcs-rmem=`0x7a000000..0x7dffffff`；CPU7 的 128 KiB
  OpenAMP 池为 `0x7a0e0000..0x7a0fffff`；日志预留 `0x7c000000..0x7c1fffff`；
  最终 ELF 入口/LOAD 为 `0x7c200000`，MMU 表从 `0x7ca00000` 起。下移到 4 GiB
  以下是为了规避当前 micad/MCS vring 地址链的 32 位截断。
- **SGI 最终裁决**：Linux `/proc/interrupts` 的左列 9 是 virq，硬件列明确为
  `GICv2 8 Edge MCS IPI`；因此最终是 **hwirq/SGI8**，不是 SGI9。内核连续
  分配 SGI0～8、Linux 使用 0～7、`mcs_km` 独占 8；UniProton 只向 CPU0 投递，
  调试期 all-other 广播已删除。CNTV tick 为 PPI11/hwirq27。
- **生命周期**：启用 `CONFIG_OS_OPTION_POWEROFF=y` 并补齐 PSCI 声明；
  `stop -> CPU7 poweroff -> start -> RPMsg echo` 可在 Linux 不重启时反复恢复。
  最终 ELF 的 1,000 轮 stop/start+451B 回显 `PASS`（746.102s）。
- **大包**：micad TTY 缓冲 256→496；UniProton 改为深度 8 held-buffer 队列、
  中断锁保护、无越界 NUL、496B TX 限幅。451B 输入形成 478B 单帧回复；
  最终 ELF 的 10,000 次顺序回显 `PASS`（4,780,000B，6.039s）。
- **生产清理与构建可靠性**：删除全部 UP7/openamp 诊断打印与临时异常向量，
  修复 `IsrRegister` 返回值、`VIRTIO_ID_RPMSG` 保护和 libmetal 空函数；修正
  libmetal 持久补丁 hunk 行数，`build_app.sh`/`build_openamp.sh` 增加 fail-fast，
  杜绝依赖失败后误用旧 ELF。最终 ELF `3faa550c...78d0`，589,064B，入口
  `0x7c200000`。
- **Yocto 正式化**：SGI8 内核补丁、MCS 496B 补丁、AutoBoot 配置、模块加载
  unit 和 micad drop-in 均已进入层；`mcs-linux` cleansstate 重建、内核 292 任务、
  最终固件更新后的镜像 2920 任务全绿。最终 boot `1b35f1d9...8001` 已写入 p3 并读回一致；
  冷启动服务 active、up0 Running、`systemctl --failed`=0。
- **当前验收**：M5 当前功能与构建范围=`COMPLETE`。72h 大包稳态与
  panic/死循环/非法访问故障注入登记为非阻塞延期补测；曾有一轮 300.09s/
  2,996 次交换的试跑，因随后清理最终调试打印而中止，不计作长稳结果。
- **报告与复现**：`stages/stage05-uniproton/docs/m5.3-single-instance-closeout.md`；
  `stages/stage05-uniproton/tests/runtime-regression.py`；
  `stages/stage05-uniproton/tests/soak-72h.py`；
  `stages/stage05-uniproton/source/overlay/uniproton-rk3572-m5-source-overlay.tar.gz`。

## 9. 阶段6：双UniProton多实例

阶段状态：`COMPLETE`（2026-09-21，当前功能与构建范围）。M6 前置、双实例资源
拆分、独立 SGI、正序/逆序并发和单边生命周期隔离均已完成。本阶段只验证多实例
资源与运行隔离，不实现主备、状态同步或表决。

### 9.1 资源分配

```text
Linux：CPU0～3、CPU6、CPU7
UP-A：CPU4（A53，MPIDR 0x100）
UP-B：CPU5（A53，MPIDR 0x101）
```

该布局保留两颗 A73 给 openEuler。M6 只验证多实例功能隔离，UP-A/B 同属 A53
cluster1 的 cluster 级共因故障不在本阶段验收范围内。最终使用
`mcs_reserve_cpus=4-5`，冷启动实测 `online=0-3,6-7`、`offline=4-5`。

资源实测定案如下：

| 资源 | UP-A | UP-B |
|---|---|---|
| CPU / MPIDR | CPU4 / `0x100` | CPU5 / `0x101` |
| notify | SGI8 | SGI9 |
| OpenAMP 池 | `0x7a080000..0x7a09ffff` | `0x7a0a0000..0x7a0bffff` |
| ELF 入口/LOAD | `0x7b200000` | `0x7c200000` |
| MMU 区 | `0x7ba00000` | `0x7ca00000` |

两实例的 ELF、resource table、vring、共享池、加载地址和 MICA client 均独立。
SGI10 未在 M6 分配，由 M7 增加第三实例时再把索引化 MCS IPI 数量从2扩为3。

初版双实例失效的根因不是共享内存重叠，而是 CPU4/CPU5 被 Linux 预留后未执行
`gic_cpu_init()`，两项 `gic_cpu_map[]` 同时保留 `0x30`，使任一 SGI 同时命中两个
保留核。最终内核在 `gic_smp_init()` 显式写入两个 GICv2 target bit；同时 MCS
用户态按 SGI 来源只唤醒对应 client。

### 9.2 MICA实例

```text
/etc/mica/tl3572-up-a.conf
/etc/mica/tl3572-up-b.conf
```

当前继续设置 `AutoBoot=no`。正序和逆序启动均已验证；保持手动模式可让 M7 在三实例
六种启动顺序和隔离测试完成前避免自动编排掩盖顺序问题。

### 9.3 双实例测试

- A→B 和 B→A 两种启动顺序均通过；
- 双路 451B RPMsg 并发：两种顺序及最终镜像烟测累计 6,000 次通过；
- 单边停启隔离：正序 50 轮/实例、逆序 20 轮/实例，合计 70 轮/实例通过；
- 50 轮后 SGI8/SGI9 计数为 1212/1202，`Err: 0`；
- 最终 Yocto 全量构建 2920/2920 成功，补丁无 fuzz、构建无 warning；
- 最终 boot 写入 p3 后按 40,647,168 字节回读，SHA256 一致；
- `systemctl --failed` 为空。

按本次收口口径，原计划中的 1,000 次随机启停由定向的 70 轮/实例正反序隔离取代；
破坏性崩溃注入放到阶段10。72 小时稳态继续登记在 M5 延期补测清单，不重复作为
M6 阻塞条件。详细证据见
`stages/stage06-multi-uniproton/docs/m6-dual-instance-closeout.md`。

退出条件：**已满足**，双实例资源隔离、任意顺序启动和独立有序恢复均已实机验证。

## 10. 阶段7：三UniProton多实例

### 10.1 CPU布局

```text
Linux：CPU0、CPU1、CPU2、CPU6、CPU7
UP-A：CPU3（A53，cluster0）
UP-B：CPU4（A53，cluster1）
UP-C：CPU5（A53，cluster1）
```

默认方案让三个副本使用同一种 A53 微架构，减少执行时延差异，并让两颗 A73 全部
服务 Linux。CPU3～5 必须由精确保留机制排除，不能再使用：

```text
maxcpus=3
```

因为它会同时让 CPU6/CPU7 下线，造成两颗 A73 闲置。

在阶段8开始确定性协议之前设置一次架构决策门：如果产品明确要求三个不同 CPU
cluster 的故障域隔离，则改为 UP-A=CPU3、UP-B=CPU5、UP-C=CPU7，Linux 使用
CPU0～2、CPU4、CPU6；同时以最慢副本为截止时间基准，补做 A53/A73 混合核型的
WCET、漂移和投票窗口测试。若无该要求，继续采用 CPU3/4/5 全 A53 默认方案。

三实例继续使用相互独立的镜像切片，入口计划为
A/B/C=`0x7b200000/0x7c200000/0x7d200000`，MMU 区为
`0x7ba00000/0x7ca00000/0x7da00000`。按 CPU3/4/5 的 128 KiB 槽位公式，OpenAMP
池为 `0x7a060000/0x7a080000/0x7a0a0000`，SGI 分别为8/9/10。M7 需先验证第三个
GIC target map 和第三路 source-directed poll，再进入三路并发。

### 10.2 三个独立固件

输出：

```text
tl3572-up-a.elf
tl3572-up-b.elf
tl3572-up-c.elf
```

三者业务代码必须来自同一提交、同一编译器和同一优化选项；仅实例ID、CPU ID、链接地址、RPMsg资源和日志地址不同。

### 10.3 三实例配置

```text
/etc/mica/tl3572-up-a.conf
/etc/mica/tl3572-up-b.conf
/etc/mica/tl3572-up-c.conf
```

服务名和endpoint必须携带实例标识，例如：

```text
tl3572.up.a.control
tl3572.up.b.control
tl3572.up.c.control
```

### 10.4 三实例验收

- 三实例同时启动；
- 三条RPMsg通道同时工作；
- 任意一个崩溃不破坏另外两个；
- 任意一个重启后重新注册服务；
- 同时压力通信；
- 72小时稳定运行；
- 串口、内核和RTOS日志能区分实例；
- 内存边界守卫和CRC没有异常。

退出条件：三个UniProton稳定共存，但还不直接控制现场输出。

预计：1～2周。

## 11. 阶段8：建立确定性三副本执行协议

### 11.1 唯一输入快照

三个实例不能各自读取现场设备，否则采样时刻不同会造成假分歧。输入代理每周期只采样一次，再将完全相同的帧发送给A/B/C。

```text
现场输入 → Input Broker → 同一InputFrame → A/B/C
```

建议帧头：

```c
struct InputFrame {
    uint32_t protocol_version;
    uint32_t epoch;
    uint64_t cycle_id;
    uint64_t sample_timestamp;
    uint32_t application_hash;
    uint32_t payload_length;
    uint32_t input_crc;
    uint8_t payload[];
};
```

### 11.2 确定性约束

- 固定周期任务；
- 固定优先级；
- 静态内存；
- 相同编译器和选项；
- 相同输入帧；
- 由cycle ID推进业务状态；
- 不直接读取各自本地时钟作为业务输入；
- 禁止随机数和未初始化变量；
- 避免依赖不确定线程执行顺序；
- 优先定点运算；
- 必须使用浮点时固定舍入模式、NaN规则和容差策略。

### 11.3 输出提案

三个实例只提交结果，不直接写 GPIO、PWM、CAN、EtherCAT 或 Modbus 输出。物理输出由
唯一表决/I/O 代理执行；输入也由 Linux 输入代理生成同一份带周期号和时间戳的快照，
避免三个实例因各自采样时刻不同产生假分歧。

```c
struct OutputProposal {
    uint32_t instance_id;
    uint32_t epoch;
    uint64_t cycle_id;
    uint32_t application_hash;
    uint32_t state_crc;
    uint32_t output_crc;
    uint32_t payload_length;
    uint8_t outputs[];
};
```

### 11.4 状态摘要

每周期至少覆盖：

- 控制状态机；
- 定时器和计数器；
- 保持变量；
- 边沿触发器；
- 上一周期输出；
- 通信状态；
- PLC/FORTE运行时关键状态；
- 应用版本哈希。

先实现 `state_crc` 一致性检查，再实现故障实例的完整检查点恢复。

### 11.5 周期时序

```text
T0：输入代理完成采样
T1：向A/B/C发布InputFrame
T2：三个实例独立执行
T3：提交OutputProposal
T4：表决截止
T5：唯一I/O代理提交现场输出
```

建议表决与输出阶段不超过控制周期预算的10%～20%。如果目标周期小于1 ms，Linux用户态表决器通常不适合作为最终实现，应改用专用裸核、FPGA/CPLD或安全MCU。

退出条件：健康状态下三实例输出和状态摘要持续一致。

预计：2～4周。

## 12. 阶段9：实现三实例2oo3表决

### 12.1 表决规则

| 收到的结果 | 动作 |
|---|---|
| A=B=C | 输出一致结果，状态3/3健康 |
| A=B≠C | 输出A/B，C进入降级/故障状态 |
| A=C≠B | 输出A/C，B进入降级/故障状态 |
| B=C≠A | 输出B/C，A进入降级/故障状态 |
| 只有两个按时到达且相同 | 降级为2oo2，允许有限时间运行 |
| 两个到达但不同 | 禁止输出，进入安全状态 |
| 只有一个到达 | 禁止输出，进入安全状态 |
| 三个都不同 | 禁止输出，进入安全状态 |
| 全部超时 | 禁止输出，进入安全状态 |

比较对象至少包括：

- epoch；
- cycle ID；
- application hash；
- output payload；
- output CRC；
- state CRC；
- 到达截止时间。

### 12.2 唯一I/O代理

```text
UP-A ─┐
UP-B ─┼→ Voter / I/O Proxy → EtherCAT、Modbus、GPIO
UP-C ─┘
```

只有I/O代理拥有现场设备。三个副本不直接打开同一个EtherCAT主站，也不能同时写同一GPIO。

功能原型允许表决器运行在openEuler Linux：

- 绑定固定CPU；
- `SCHED_FIFO`；
- `mlockall`；
- 启动时预分配全部内存；
- 不在周期内进行日志落盘；
- 使用无锁环形队列或预分配队列；
- 外部watchdog监视表决器。

产品化时，表决器仍是单点。若要求更高完整性，需迁移至独立CPLD/FPGA、安全MCU或第四个专用裸核组件。

### 12.3 健康状态机

```text
OFFLINE
  → STARTING
  → SYNCING
  → HEALTHY
  → DEGRADED
  → FAULTED
  → RESTARTING
  → SYNCING
```

故障实例重新加入步骤：

1. 表决器把实例标记为FAULTED；
2. 停止实例；
3. 清理旧vring和服务；
4. 重新加载ELF；
5. 恢复最近检查点；
6. 进入SYNCING；
7. 连续N个周期与多数状态、输出一致；
8. 转为HEALTHY；
9. 重新参与2oo3投票。

实例重启后禁止立即获得投票权。

### 12.4 防止旧包和重复包

- epoch在系统重新编组时增加；
- cycle ID严格递增；
- 丢弃旧epoch、旧周期和未来周期包；
- 每实例维护最后接收序号；
- 同周期重复提案只接收第一次有效版本；
- CRC错误直接标记无效；
- 应用版本不一致不得加入表决组。

### 12.5 安全输出策略

项目必须明确：

- 输出最多保持最后值多长时间；
- 何时输出归零；
- 电机、阀门、继电器的安全位置；
- EtherCAT失联动作；
- 两实例失效后的动作；
- 表决器失效后的外部watchdog动作；
- Linux重启时RTOS输出是否立即禁止。

退出条件：任意一个实例错误、停止或迟到时，多数结果仍能正确输出；两个实例失效时系统进入安全状态。

预计：

- 通用确定性任务2oo3：3～6周；
- 加入PLC完整状态：再增加3～6周；
- 加入EtherCAT闭环：再增加4～8周。

## 13. 阶段10：故障注入与最终验收

### 13.1 软件故障注入

- 单实例panic；
- 死循环；
- 栈溢出；
- 输出bit翻转；
- 状态CRC错误；
- RPMsg丢包、重复、延迟、乱序；
- 错误epoch/cycle ID；
- 单实例重启；
- micad重启；
- 表决器进程重启。

### 13.2 资源和负载故障

- 单核无响应；
- 中断风暴；
- RPMsg flood；
- DDR带宽压力；
- Linux CPU和内存高负载；
- CPU升降频；
- 高温降频；
- EtherCAT断线重连；
- 电源循环；
- 连续冷启动。

### 13.3 2oo3最终验收条件

1. 三实例正常时3/3一致；
2. 任一实例停止，系统在规定时间内降级运行；
3. 任一实例给出错误输出，错误被多数表决屏蔽；
4. 任一实例迟到，过期结果不能进入输出；
5. 两实例失效，系统进入安全状态；
6. 故障实例恢复后先同步，再重新加入；
7. 恢复过程不产生一次错误脉冲；
8. 表决器失效时外部watchdog触发安全动作；
9. 三实例连续运行不少于72小时；
10. 自动故障注入不少于10000次且无不安全输出；
11. 所有构建产物可由固定清单重新生成；
12. 完整厂商update.img仍可在Loader模式下恢复板卡。

### 13.4 最终交付物

```text
meta-tl3572/
tl3572-openeuler-rootfs.ext4
tl3572-mica-boot.img
tl3572-openeuler-mica-update.img
tl3572-up-a.elf
tl3572-up-b.elf
tl3572-up-c.elf
/etc/mica/tl3572-up-{a,b,c}.conf
2oo3-protocol.md
input-broker
voter-io-proxy
fault-injection-suite
version-manifest.json
SHA256SUMS
build-logs/
serial-logs/
test-report.md
rollback-guide.md
```

## 14. 时间和里程碑

按1名熟悉Linux/RTOS的工程师全职估算，不包含IEC 61131-3运行时从零移植和安全认证：

| 里程碑 | 累计预估 | 当前状态 |
|---|---:|---|
| 远端工作区和版本基线完成 | 0.5～1天 | `COMPLETE`，2026-09-15实测通过 |
| openEuler rootfs在TL3572启动 | 2～4天 | `PARTIAL_PASS`，2026-09-15已启动并通过串口/网络/SSH主路径，待镜像清理和稳定性测试 |
| meta-tl3572可重复构建 | 1～2周 | `COMPLETE`，2026-09-16：M1/M2 构建与实机验收全部通过，完整 update.img 已生成并整镜像烧录复验（`--failed`=0）；稳定性测试顺延至阶段4 |
| Linux MICA基础可用 | 2～4周 | `COMPLETE`，2026-09-17：M4a-d 实机验证、Yocto 正式化、完整 update.img 三重验证及整镜像实机复验全部通过；M4e 的模块压测与稳定性测试作为阶段 4 非阻塞保留待办，后续查缺补漏时执行 |
| 单UniProton稳定 | 4～7周 | `COMPLETE`（当前功能与构建范围），2026-09-18：M5.1/M5.2/M5.3 闭环，最终 ELF 10,000 次大包与 1,000 次启停通过，最终 Yocto boot 冷启动/AutoBoot 通过；72h 稳态和三类故障注入作为非阻塞延期补测 |
| 双UniProton稳定 | 5～9周 | `COMPLETE`（当前功能与构建范围），2026-09-21：CPU4/5 双实例、SGI8/9、正反序并发、70 轮/实例单边停启和零警告全量构建通过；72h 仍归 M5 延期补测 |
| 三UniProton稳定 | 6～11周 | `NOT_STARTED`；默认 CPU3/4/5 A53，Linux 使用 CPU0～2/6/7；阶段8前决定是否切换跨 cluster 方案 |
| 通用负载2oo3功能原型 | 2～4个月 | `NOT_STARTED` |
| PLC状态同步＋EtherCAT工程原型 | 4～7个月 | `NOT_STARTED` |

## 15. 关键风险

| 风险 | 缓解措施 |
|---|---|
| MCS代码与Linux 6.12 remoteproc API不兼容 | 先建立最小编译补丁集，逐接口适配并保留内核符号检查 |
| TF-A/PSCI不能重复拉起指定核 | 2026-09-18 已用最终 ELF 完成 1000 次 stop/start+RPMsg echo，全部通过；72h 长稳列为后续补测 |
| 非连续 CPU 保留失败，误让 A73 下线或被 Linux 拉起 RTOS 核 | CPU4/5 双实例已于 2026-09-21 用 `mcs_reserve_cpus=4-5` 实机闭环：CPU6/7 online、CPU4/5 present/offline；M7 扩展 CPU3 时重复同一验收，禁止退回 `maxcpus` 或用户态临时热下线 |
| 三实例IPI或vring冲突 | M6 已验证两路独立 SGI、共享池和 source-directed poll；M7 新增 SGI10 与第三池后重复正反序、边界和单边恢复检查 |
| 三个 A53 副本未覆盖三个 cluster 的共因故障 | 阶段8前设置决策门；需要 cluster 级隔离时改用 CPU3/5/7，并验证 A53/A73 混合核型时序 |
| Cache一致性导致偶发数据错误 | 统一共享内存属性，加入屏障、CRC和flood测试 |
| 4 GiB地址空间与厂商保留区冲突 | 以完整DTS和/proc/iomem为唯一依据，不复制其他SoC地址 |
| 三副本因非确定性产生假分歧 | 单一输入快照、固定周期、静态内存、定点运算 |
| EtherCAT、CAN、GPIO 等被多个副本同时控制 | `eth1` 和所有现场输出仅归 Linux 唯一表决/I/O 代理所有；RTOS 只提交提案 |
| Linux 输入代理或表决器成为单点 | 外部 watchdog 与输出使能闭锁；M9 后按安全目标评估迁移到 FPGA/CPLD 或安全 MCU |
| 同芯片共因故障 | 明确能力边界；高可用/安全产品最终采用双板或外部安全岛 |
| 远端共享源码被覆盖 | TL3572使用独立目录，不清理、不重置现有仓库 |

## 16. 官方资料

- [openEuler Embedded oebuild构建指导](https://pages.openeuler.openatom.cn/embedded/docs/build/html/openEuler-24.03-LTS/oebuild/userguide/build/index.html)
- [openEuler Embedded新增BSP层指南](https://pages.openeuler.openatom.cn/embedded/docs/build/html/master/developer_guide/develop/board-support/add_new_bsp_layer.html)
- [MICA构建指导](https://pages.openeuler.openatom.cn/embedded/docs/build/html/master/features/mica/mica_core/build.html)
- [MICA使用指导](https://pages.openeuler.openatom.cn/embedded/docs/build/html/openEuler-24.03-LTS/features/mica/instruction.html)
- [MICA命令与配置文件](https://pages.openeuler.openatom.cn/embedded/docs/build/html/openEuler-24.03-LTS/features/mica/mica_ctl.html)
- [RTOS资源表与OpenAMP接入](https://pages.openeuler.openatom.cn/embedded/docs/build/html/openEuler-24.03-LTS/features/mica/developer_guides/rtos.html)
- [UniProton ARM64多实例需求](https://gitee.com/openeuler/UniProton/issues/I9ADDM)
- [openEuler 24.03 LTS SP2 Embedded测试报告](https://gitee.com/openeuler/QA/blob/master/Test_Result/openEuler_24.03_LTS_SP2/openEuler-24.03-LTS-SP2%20embedded%E7%89%88%E6%9C%AC%E6%B5%8B%E8%AF%95%E6%8A%A5%E5%91%8A.md)
