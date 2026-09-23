# TL3572 阶段4 Yocto 正式化记录（2026-09-16 19:05）

承接 `stage04-m4-validation-and-cpu-reservation.md`。本会话完成阶段4 最后一项：
内核成果 Yocto 化 + 完整 update.img 交付。M4e 压测/稳定性按用户决策继续顺延。

阶段状态：`COMPLETE`（2026-09-17）。M4e 的 1000 次模块压测、10 次冷启动和 24 小时稳定性测试保留为阶段 4 非阻塞待办，后续查缺补漏时执行，不影响进入阶段 5。

## 1. 侦察结论（动手前）

- 生效构建目录 `build/build-tl3572/`（bblayers 只挂 meta-tl3572-stage3）；机器配置
  `PREFERRED_PROVIDER_virtual/kernel = "linux-dummy"`，注释明确预留 linux-tl3572 provider 落地点；
- 厂商模块/固件走 `tl3572-vendor-assets`（tarball 直装 /lib/modules + /lib/firmware）；
- 构建脚本 `remote-build-stage3-m2.sh` 按记忆规则 sed 派生为 `remote-build-stage4.sh`；
- 服务器 crontab 已有当日守卫（`!= 20260916` 才执行 17:01 关机/智能关机），整夜构建安全，
  **次日 17:01 恢复自动关机**，长构建需重新设守卫；
- 全量源码 diff（tarball 纯净树 vs build-kernel）确认改动仅 4 文件：
  smp.c、smp.h、两份 tl3572-evm.dts（dts 改动不进配方——boot 用 vendor.dtb+overlay 路线）；
  **此前保存的 0001 补丁漏了 smp.h**（无 .orig 备份），本次从纯净树重新生成完整版；
- `scripts/module-common.c` 是厂商内核树自带，kbuild 自动链入外部模块（.module-common.o），
  配方只要用厂商树编模块即可复现，无需额外处理。

## 2. linux-tl3572_6.12.69.bb（meta-tl3572-stage3/recipes-kernel/linux/）

- files/ 十件套：重打包 tarball（270,581,126B，顶层目录版，roundtrip 校验）、0001 完整补丁
  （55 行，patch -p1 --dry-run 验证）、v4 defconfig（57e11529...）、localversion、
  vendor-boot.img（4f2bbfb2...）、tl3572-mcs-overlay.dts、boot-mcs.its、mcs_km.c + Makefile、
  0003 适配记录补丁；
- 非 provider 设计 + Arm 14.3 工具链 PATH 注入 + 四重断言
  （utsrelease / vermagic / vendor.dtb+resource+fdt 三 SHA / FIT 内哈希）；
- 断言全部经预验证：配方 sysroot 的 dtc/fdtoverlay/dumpimage 产出与板上验证产物
  逐字节一致（fdt=195535eb...）后才启动构建。

## 3. 构建三轮踩坑（最终 2920 任务全绿）

| 轮次 | 失败点 | 根因 | 修复 |
|---|---|---|---|
| 1 | mcs-km 模块 make exit 2 | 层文件名 mcs-km-Makefile，subdir 落地后 kbuild 找不到 Makefile | 改名 Makefile |
| 2 | vermagic 断言"看似相等实不等" | `grep -ao 'vermagic=[^ ]*...'` 的 `[^ ]*` 吞 NUL 后整段 .modinfo，bash 命令替换静默丢 NUL | 改 `grep -aq` 固定串 |
| 2b | 解析失败 | 修 vermagic 时内联 heredoc 吃反斜杠，留下孤立 `\n` 与 `fi` | 文件传输无损路径修；启动前先 `bitbake -p` 解析检查 |

产物（deploy/images/tl3572-evm/）：Image 40,081,920B（aa1e9c9e...）、
boot.img 40,647,168B（f0303cb4...，FIT 内 fdt 哈希=195535eb 与验证版一致）、
mcs_km.ko 95,488B（c38973bc...）、config（57e11529...）。
manifest：`linux-tl3572 tl3572_evm 6.12.69` 在列，nfs 计数 0，
rootfs /lib/modules 8 个 .ko（7 厂商 + mcs_km）。

## 4. 完整 update.img（`stages/stage04-mica-mcs/release-update-20260916/`）

- rootfs 缩容 4,294,967,296→3,999,997,952（resize2fs 3906248K + e2fsck 双检，5cdd9cc5...）；
- AFPTool v2.28 -pack 十件套（8 件厂商原件复用 stage3 已验证素材 + 新 boot + 缩容 rootfs）
  → firmware.img 4,118,360,068B；
- RKFW python 组装（`../logs/assemble-rkfw-stage4.py`）：
  厂商头（仅 fw_size@0x25 改 4,118,360,068）+ 厂商 boot 区 + firmware + 32B MD5；
  **脚本先自检**：厂商 firmware 重组厂商镜像 → 与原件 SHA256 逐字节一致（c66ffb62...）；
- update-tl3572-openeuler-stage4.img 4,119,186,108B，SHA256 6eafe110...860ecf；
- 三重回解验证：RKImageMaker -unpack success（firmware 99569d34 一致；boot.bin =
  MiniLoaderAll.bin = 厂商 boot 区 bd3c4eab）；AFPTool -unpack firmware 10 分区逐字节一致；
  头部 diff 仅 fw_size 3 字节。AFPTool -unpack 直接吃重组 update.img 报 check crc failed
  属固有行为（stage3 已实机验证镜像同样报错），非本镜像缺陷。

## 5. 板卡与服务器结项状态

- 板卡：阶段 4 完整整镜像已于 2026-09-16 19:27 烧录并实机复验通过；运行 Yocto
  配方产出的 `6.12.69-gf1b67c293213` 内核，CPU7 预留，`systemctl --failed` 为 0，
  `mcs_km` 加载/卸载及 `micad`、`mcsctl status` 均验证通过；
- 服务器：meta-tl3572-stage3 已含新配方；build-kernel/.config.pre-maxcpus-20260916 为
  修改前备份；kernel-src-pristine/（纯净树）与 kernel-src-vendor.tar.gz 保留作溯源；
  明日 17:01 起恢复自动关机。

## 6. 阶段 4 保留待办（不阻塞结项）

- M4e：10 次冒烟 + 1000 次模块压测、冷启动 10 次 + 24h 稳定性（用户决策顺延，以后查缺补漏）；
- 下一步进入阶段5：单 UniProton 移植（RK3572 板级目录 + rpmsg_echo + CPU7 实例配置，
  替换 micad 默认的 rpi4/CPU3 实例配置）。
