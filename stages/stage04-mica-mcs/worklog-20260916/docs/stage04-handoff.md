# TL3572 阶段4 交接文档（2026-09-16 15:15 暂停）

> 交接原因：Stage4 首轮 boot.img 烧录后板卡停在 U-Boot 提示符，未启动。正在串口诊断时用户暂停，要求交接。
> 接手模型请先读本文件，再读主文档《TL3572_openEuler_MICA_UniProton_2oo3_完整移植路径.md》（阶段0-3全部完成，阶段4进行中）。

## 1. 当前状态一句话

内核/DTB/mcs_km.ko 全部构建成功（vermagic 精确复现厂商 `6.12.69-gf1b67c293213`），重组的 boot.img 烧入后 **U-Boot 拒绝启动，停在 `=>` 提示符**，错误线索为 `No valid android hdr`。这是唯一的阻塞点。

## 2. 板卡现场（重要）

- 板卡当前停在 **U-Boot 交互提示符**（串口 COM7，115200 8N1，CH340 线）
- SSH root@192.168.2.143 不可达（系统未启动）。板卡正常时 SSH 可用：`plink -ssh -batch -hostkey 'SHA256:60CU6EkU00yhkNXzA1B87ln0nyy0+A5Oaubdn7fYn44' -pw '' root@192.168.2.143`（空密码）
- **板卡可随时回滚**：按住升级键进 Loader 模式，RKDevTool「下载分区」只烧 boot 分区（地址 0x0000a000），文件用厂商原版 `I:\TL3572-EVM(Buildroot-2026.02)_Alpha_V1.1\4-软件资料\Linux\Kernel\image\linux-6.12.69-v1.0-gf1b67c2\boot.img`（SHA256 与 update.img 内的一致，已验证）
- U-Boot 下手动 `boot` 的完整输出已存 `logs\uboot-diag.txt`，关键行：
  ```
  ANDROID: reboot reason: "(none)"
  Not AVB images, AVB skip
  No valid android hdr          ← 关键失败
  Android image load failed
  Android boot failed, error -1.
  ## Booting FIT Image FIT: No fit blob
  FIT: No FIT image
  Scanning for bootflows in all bootdevs
  Card did not respond to voltage select! : -110   (mmc@2a090000, SD卡槽, 可忽略)
  (0 bootflows, 0 valid)
  ```

## 3. 失败分析与排查线索（按优先级）

我们的 boot.img 与厂商 boot.img 的已知差异**只有一个**：FIT 的 `configurations/conf` 里删掉了 `signature` 节点（原 ITS 含 `signature { algo="sha256,rsa2048"; padding="pss"; key-name-hint="dev"; sign-images=... }`）。当时依据：rk3572_defconfig 只有 `CONFIG_SPL_FIT_FULL_CHECK=y`、无 `CONFIG_FIT_SIGNATURE`，且板子 cmdline `androidboot.verifiedbootstate=orange` → 判定 U-Boot proper 不校验签名 → 删节点打包。**现在看这个推断可能不完整**：Rockchip 的 android 启动路径（`boot_android`）对 FIT 镜像的"hdr 校验"可能要求 signature 节点存在（哪怕不验证内容）。

### 线索A（最优先）：确认烧录内容真实落盘
U-Boot 串口下执行（每条命令间等输出）：
```
mmc list
mmc dev 0          # 找到 eMMC（mmc@2a010000 或 2a090000，按 list 输出确定）
mmc read ${loadaddr} 0xa000 0x10
md.b ${loadaddr} 0x20
```
- 期望前 4 字节 `d0 0d fe ed`（FIT 魔数）= 我们烧的镜像在
- 若不是 → RKDevTool 烧录地址/分区名不对，重新烧（boot@0x0000a000，注意是**下载分区**模式手动填地址，不是烧整包）
- 同时 `printenv bootcmd` 记录厂商启动链，看 android→FIT 的顺序与条件

### 线索B：signature 节点假设验证/修复
1. 重新打包一版 **保留 signature 节点**的 ITS（不删节点，mkimage 不带 -k 时会在 signature 节点留空值——若 mkimage 报错则改用 `-k` 生成自签名密钥，反正 U-Boot 不校验内容，或者把厂商 boot.img 里的 signature 值原样拷进 ITS）
2. 打包命令在构建机 `/home/openeuler/build/tl3572-2oo3/bootimg-out/`，mkimage 用 dnf 装的 `/usr/bin/mkimage`
3. 深挖（如B无效）：用 `dtc -I dtb -O dts` 全文 diff 厂商 FIT vs 我们 FIT（vendor 在容器 `/home/openeuler/vendor-boot.img`），逐属性对比 configurations/defaults/结构差异（timestamp、`default` 属性、hash 节点位置等）

### 线索C：U-Boot 源码确认（材料齐全）
- U-Boot 源码在构建机 `/home/openeuler/build/tl3572-2oo3/u-boot-2025.04/`（含 .git？无，tar 平铺后移入该目录）
- 直接 grep：`grep -rn "No valid android hdr" u-boot-2025.04/` 找到打印处，逆推校验条件——这是最确定性的路径
- 相关文件预计在 `common/android_boot.c`、`cmd/bootm.c`、`common/image-fdt.c` 或 `arch/arm/mach-rockchip/`

### 线索D：换思路绕开
若 signature/android hdr 问题难解，备选：
- 用厂商 FIT 的 **结构克隆法**：`dumpimage` 逐节点提取厂商 FIT 的所有属性，只替换 kernel/fdt 数据 blob 与 hash 值（python 脚本二进制级替换，FIT 是 dtb，hash 是 sha256 值直接改写）
- 或阶段4拆两步：先用厂商原版 boot.img 验证（确认串口/烧录流程无误），再攻打包差异

## 4. 已完成并验证的工作（不需要重做）

### 4.1 内核（构建机 `/home/openeuler/build/tl3572-2oo3/build-kernel/`）
- 源码：厂商 `linux-6.12.69-v1.0-gf1b67c2.tar.gz`（SHA256 `186face388...d60608` 与阶段1清单一致），平铺解压在 build-kernel/ 根
- 工具链：`/home/openeuler/build/tl3572-2oo3/toolchain-14.3/`（aarch64-none-linux-gnu-gcc 14.3.1，**必须用这个**，厂商内核就是它编的；不能用 openEuler gcc 12.3）
- .config：板上 `/proc/config.gz` 原样种子（md5 `51ecac4f...`）+ `scripts/config -e REMOTEPROC RPMSG_CHAR RPMSG_CTRL`
- 版本号：根目录 `localversion` 文件内容 `-gf1b67c293213`（原 .git 是死链已删）；`include/generated/utsrelease.h` 确认 `6.12.69-gf1b67c293213`
- IPI 补丁：`arch/arm64/kernel/smp.c`（`set_smp_ipi_range` 后追加 `arm64_mcs_ipi_virq()`/`arm64_mcs_ipi_send()`，EXPORT_SYMBOL_GPL，声明加在 `arch/arm64/include/asm/smp.h`）+ `patches/0001-*.patch`；System.map 已确认 4 个符号（含 ksymtab）
- 原理：GICv3 只把 SGI 0-7 分给内核 IPI（`set_smp_ipi_range(base_sgi, 8)`），SGI 8 空闲留给 mcs_km
- 产物：`arch/arm64/boot/Image`（40,081,920B）、模块全套。**构建命令模式见 §6 坑1**

### 4.2 DTB
- `arch/arm64/boot/dts/rockchip/tl3572-evm.dts`：根节点 `compatible` 行之后插入（**属性必须先于子节点**，dtc 会拒）：
  ```dts
  reserved-memory { #address-cells=<2>; #size-cells=<2>; ranges;
      mcs_rmem: mcs-rmem@134000000 { reg=<0x1 0x34000000 0x0 0x04000000>; no-map; }; };
  mcs_remoteproc: mcs-remoteproc { compatible="oe,mcs_remoteproc"; memory-region=<&mcs_rmem>; };
  ```
- 选址依据：板上 /proc/iomem 主 RAM `0x49400000-0x13fffffff`，顶部 `0x13af18000+` 已有保留（OP-TEE类），`0xfb000000-0x101ffffff` 是 128M CMA；选 `0x134000000` 64MiB（16M SHM + 36M 实例 + 余量，对应 mcs_km 的 `OPENAMP_SHM_SIZE=0x1000000`/`INSTANCE_SIZE=0x2400000` 布局）
- 已验证 dtb 反编译正确挂在 `/reserved-memory/` 和 `/` 下；`0002-tl3572-dts-mcs-reserved-memory.patch` 已存

### 4.3 mcs_km.ko（构建机 `/home/openeuler/build/tl3572-2oo3/mcs-km-tl3572/`）
- 原版：`src/mcs/mcs_km/mcs_km.c`（597行，单文件模块，openEuler mcs 仓库 5cb4915）
- 移植点（已完成的改动，源文件 `mcs_km-tl3572.c`）：
  1. 删 `#define IPI_MCS 8` 硬编码，改 `static int mcs_irq = arm64_mcs_ipi_virq()` 运行时解析
  2. `ipi_send_mask(IPI_MCS, mask)`（内核未导出的静态函数）→ `arm64_mcs_ipi_send(mask)`
  3. 其余 percpu IRQ 操作换 mcs_irq；PSCI smc/hvc、kprobe cpu_logical_map（6.12 符号仍在）不动
- 编译产物 `mcs_km.ko`（69,528B）vermagic `6.12.69-gf1b67c293213 SMP mod_unload aarch64`（与厂商内核/板上7个模块逐字符一致）

### 4.4 boot.img（构建机 `bootimg-out/`）
- 组成：boot.its（源码树根自带，厂商 FIT 配方）去掉 signature 节点 → boot-mcs.its
- `kernel`→新Image、`fdt`→新dtb（软链接）、`resource`→厂商原版（`dumpimage -T flat_dt -p 2 -o resource.img /home/openeuler/vendor-boot.img` 提取，300,544B）
- `mkimage -f boot-mcs.its boot.img` = 40,646,878B；`dumpimage -l` 验证 3 镜像+hash 正常
- **这就是当前起不来的镜像**（Windows 副本 `../artifacts/boot-mcs-tl3572.img`，SHA256 `58ce18747af5ccb93c37e3383ad53949187318b8a34595a22d97924e57f95b1a`）

### 4.5 板上验收清单（修好启动后照此跑）
```
zcat /proc/config.gz | grep -E 'REMOTEPROC=|RPMSG_CHAR=|RPMSG_CTRL='   # 应 =y（新内核证明）
uname -r                                    # 仍是 6.12.69-gf1b67c293213
grep 134000000 /proc/iomem                  # 该段不再是 System RAM
ls /proc/device-tree/mcs-remoteproc/
scp mcs_km.ko 板:/root/ && insmod /root/mcs_km.ko && ls -l /dev/mcs
dmesg | grep mcs                            # 应见 assign memory region 0x134000000.. / mcs 注册日志
rmmod mcs_km && insmod ...（循环；1000次压测属 M4e）
systemctl start micad && mcsctl status      # micad active、无实例（无RTOS固件属预期）
```

## 5. 环境/通道速查

| 项 | 值 |
|---|---|
| 构建宿主机 | 10.100.60.226，root 登录凭据仅在本地保存，plink hostkey `SHA256:VTBdf30zWtBqP73//d9S9oYVOb3wrWZZdQPdwO87m1Y` |
| 构建容器 | `docker exec dev_openeuler`，**必须 `-u openeuler -e HOME=/home/openeuler`**（root 会被 bitbake 拒；root 建的文件要 chown） |
| 工作区 | `/home/openeuler/build/tl3572-2oo3/`（内核=build-kernel/，模块=mcs-km-tl3572/，打包=bootimg-out/，U-Boot=u-boot-2025.04/，工具链=toolchain-14.3/） |
| mkimage/dumpimage | 容器 `/usr/bin`（`dnf install uboot-tools` 装的；u-boot 源码 tools-only 编译因 Kconfig 交互卡死放弃） |
| 板卡串口 | COM7（CH340）`plink -serial COM7 -sercfg 115200,8,N,1,N`；**stdin EOF 后 plink 不退出，用完 powershell Stop-Process plink** |
| 板卡 SSH | root@192.168.2.143 空密码，hostkey `SHA256:60CU6EkU00yhkNXzA1B87ln0nyy0+A5Oaubdn7fYn44`（当前系统未起不可用） |
| 传文件 | 容器→宿主 `docker cp`，宿主→Windows `pscp`（单文件单命令，多源不支持）；plink/pscp stdout 会 CRLF 污染二进制，传文件只能 pscp |
| 厂商 boot.img 参照 | 容器 `/home/openeuler/vendor-boot.img`；本地 `4-软件资料\Linux\Kernel\image\...\boot.img` 与 afp-unpack/boot.img 同一文件 |
| Windows 工作目录 | `stages/stage04-mica-mcs/worklog-20260916/`（artifacts/ + logs/ + docs/） |

## 6. 已踩过的坑（接手别再踩）

1. **远程脚本**：一律本地写 .sh → `tr -d '\r'` → `plink "docker exec -i -u openeuler ... bash -s" < 脚本`。内联 heredoc 嵌套引号必炸
2. **反斜杠会被传输链吃掉**：python 里写 C 的 `\n` 字面量要用 `chr(92)+chr(110)` 拼接，别用 `\\n`
3. **内核 make 非交互**：所有 make 加 `< /dev/null`；出现 "Error in reading or end of file" = Kconfig 有新问题，先 `make olddefconfig < /dev/null`（u-boot 用 `yes '' | make oldconfig`）
4. **模块编译**：必须 `export PATH=toolchain/bin:$PATH ARCH=arm64 CROSS_COMPILE=aarch64-none-linux-gnu-` 后 `make KERNEL_SRC=build-kernel`；若报 host gcc 不认识 `-fmin-function-alignment` = 环境变量没传进去
5. **dts 语法**：属性必须先于子节点；插入锚点选 `compatible` 行后；`rfind("\n};")` 定位根节点结束不可靠（会掉进 thermal-zones）
6. **pkill**：`pkill -f "u-boot"` 会匹配到自己 docker exec 的命令行把会话杀掉，用 `pkill -x make`
7. **plink 串口**：脚本化发送用 `{ sleep; printf 'cmd\r'; } | plink -serial ...`，采集文件在 pipe 左侧生成；结束后必须杀 plink
8. **U-Boot tools-only 源码编译**：Kconfig 交互死循环（AVB_BUF_ADDR 等），已放弃改用 dnf 包

## 7. 阶段4 任务全景（M4a-M4e）

| 任务 | 状态 |
|---|---|
| M4a 摸底 | ✅ 完成（配置/内存图/源码/工具链全定位） |
| M4b 新内核+boot.img | 🔶 构建全通过；**实机启动失败（本文件主线问题）** |
| M4c mcs_km 适配 | 🔶 模块已编译通过；板上加载验证等 M4b 修复 |
| M4d DTB 保留内存 | 🔶 DTB 已改好并进 boot.img；板上 /proc/iomem 验证等 M4b 修复。剩余：CPU 预留（maxcpus=7 或 offline CPU7，计划放第二轮烧录，与阶段5衔接） |
| M4e 验收收口 | ⬜ 等 M4b/c/d 板上通过后：1000次模块压测、micad/mcsctl、文档、稳定性测试（冷启动10次+24h，用户已明确顺延） |
| 后续正式化 | ⬜ 内核成果固化为 meta-tl3572-stage3 的 linux-tl3572_6.12.bb（Yocto 化，见主文档 §6.3/7.x 计划）；IPI 补丁与 mcs_km 移植入库 |

## 8. 关键文件索引

- 主进度文档：`I:\...\TL3572_openEuler_MICA_UniProton_2oo3_完整移植路径.md`（§6.7 是阶段3收口记录；阶段4尚未写入，需接手者补 §7 实测记录）
- 阶段3 交付：`stages/stage03-yocto-bsp/release-update-m2-20260916/`（完整 update.img 已实机验证 --failed=0）
- 阶段4 Windows 产物：`../artifacts/`（boot-mcs-tl3572.img / mcs_km.ko / 0001/0002 补丁 / mcs_km-tl3572.c / boot-mcs.its / kernel-config-stage4-mica / SHA256SUMS）
- 串口证据：`../logs/`（board-kernel-recon.txt=刷前摸底，serial-post-flash-stage4.txt=停在U-Boot，uboot-diag.txt=手动boot完整输出）
- 服务器侧快照：修改前原件 `*.orig-20260916`（smp.c、tl3572-evm.dts）；容器临时导出目录已清理
