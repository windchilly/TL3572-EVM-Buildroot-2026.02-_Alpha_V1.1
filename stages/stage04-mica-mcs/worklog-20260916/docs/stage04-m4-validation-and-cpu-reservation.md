# TL3572 阶段4 补验与 CPU 预留记录（2026-09-16 17:45）

承接 `stage04-handoff.md`（15:12 暂停）与
`../artifacts/实机验证结果-20260916.txt`（16:59 v3 实机验证）。
本会话完成：①M4b/c/d 板上补验；②CPU 预留（maxcpus=7，v4 镜像，实机验证）；③主文档 §7 实测记录补写。

## 1. 板上补验（v3 内核，17:14–17:17）

| 项 | 实测 | 状态 |
|---|---|---|
| /proc/config.gz | `CONFIG_REMOTEPROC=y` `CONFIG_RPMSG_CHAR=y` `CONFIG_RPMSG_CTRL=y`（另 RPMSG_NS/RPMSG_VIRTIO/HOTPLUG_CPU/OF_RESERVED_MEM 均 =y；对比厂商内核这三项为 not set） | PASS |
| uname | `6.12.69-gf1b67c293213 #2 SMP Wed Sep 16 13:48:38 CST 2026`（重编内核在板上运行） | PASS |
| insmod mcs_km-tl3572-of-cpu.ko | RC=0，`/dev/mcs` 508:0 创建；上板 SHA256 复核 `1c42336c...aadb` 一致 | PASS |
| systemctl start micad | active (running) | PASS |
| mcsctl status | RC=0；`uniproton` / `uniproton-gdb` 两实例 Offline（指向不存在的 `/lib/firmware/rpi4-*.elf`，属预期——尚无 RTOS 固件） | PASS |
| rmmod | RC=0，模块与 /dev/mcs 清理干净，无 oops | PASS |

## 2. CPU 预留：U-Boot env 路线排查（不可行，已定性）

首试"串口中断自启 + 改 env bootargs"（CR 连发），失败。`logs\serial-cpu-reserve-session1.txt`
完整记录了这次重启，两个决定性证据：

1. `Loading Environment from nowhere... OK`（第 466 行）——厂商 U-Boot 为 **ENV_IS_NOWHERE**，
   env 不落盘，`saveenv` 无法持久化；
2. `Hit key to stop autoboot('CTRL+C'): 0`（第 500 行）——自启打断只认 **CTRL+C** 且倒计时 **0**，
   CR 连发无效。

结论：厂商 U-Boot 上 env 路线死路，cmdline 只能内核固化。
（该日志同时完整记录了 v3 的 DDR 训练/SPL/TF-A/OP-TEE/U-Boot 启动链与 FIT 校验过程，可作参考。）

## 3. v4 内核：CONFIG_CMDLINE_FORCE + maxcpus=7

- arm64 6.12 的 Kconfig choice 只有 `CMDLINE_FROM_BOOTLOADER`/`CMDLINE_FORCE`（**无 EXTEND**，
  与 arm32/x86 不同）→ 采用 FORCE 整串固化；
- 固化串 = 板上实测 U-Boot 传递的 cmdline 逐字复制，仅去掉纯信息性的 `androidboot.fwver`
  （随固件版本过期）并追加 `maxcpus=7`；内核实际消费的 earlycon/console/root/rootwait/rw/rcu_*
  全保留；`androidboot.*`/`storagemedia` 本就被内核视为未知参数透传用户态，openEuler rootfs
  不读取，冻结无功能影响；
- 增量重编仅 relink（NM/SORTTAB/OBJCOPY），utsrelease 保持 `6.12.69-gf1b67c293213` →
  **mcs_km-tl3572-of-cpu.ko 无需重编**，vermagic 仍匹配；
- FIT v4 完全复用 v3 的 fdt（厂商 DTB + mcs overlay + ufs@29e00000 disabled，SHA `195535eb...`）、
  resource（`7508f47d...`）与外置数据格式（`mkimage -B 0x200 -E -p 0x800`），仅 kernel blob 更新
  （SHA `7530ff3b...`）；
- 产物：boot.img 40,647,168 字节，SHA256
  `5bdd356b66f51e758277724df16836a3086190d999101a35fdf31d7506158691`；
- 归档：服务器 `bootimg-out-stage4-external-fit-v4-maxcpus/`；本地
  `tl3572-stage4-external-fit-v4-maxcpus-20260916\`（含烧录说明.txt、config-diff.txt、
  kernel-config-v4-maxcpus）；修改前 .config 备份为服务器 `build-kernel/.config.pre-maxcpus-20260916`。

## 4. 烧录与实机验证（17:40–17:42，v4）

烧录方式：**板上 Linux 直写 boot 分区** `/dev/mmcblk0p3`（64 MiB，对应 RKDevTool 地址
0x0000a000；parameter.txt 分区表：p1=uboot p2=misc p3=boot p4=recovery p5=backup
p6=rootfs p7=oem p8=userdata）。三重防护：镜像 SHA 校验、p3 现存 FIT 魔数 `d00dfeed`、
p3 尺寸 131072 sectors；烧前备份 p3 原内容至 `/root/boot-p3-backup-pre-v4.img`
（64 MiB，SHA `96919338f0ccaddc037e0c053b6fd103621319f8f6f08a78920c118aa865f58c`）；
dd 后回读 SHA 精确匹配。

（串口捕获因 COM7 被本机占用报 Error 5 失败，证据改用 SSH + dmesg，内容等价。）

| 验收项 | 实测 | 状态 |
|---|---|---|
| /proc/cmdline | 固化完整串，末尾 `maxcpus=7`，无 U-Boot 动态追加段 | PASS |
| CPU 状态 | nproc=7；online `0-6`；offline `7`；present `0-7` | PASS |
| dmesg | `smp: Brought up 1 node, 7 CPUs`；`SMP: Total of 7 processors activated`；全日志 CPU7 出现 0 次（从未进入 Linux） | PASS |
| mcs 保留内存 | `/proc/iomem` `134000000-137ffffff : reserved`；dmesg nomap `mcs-rmem@134000000` 64 MiB | PASS |
| mcs-remoteproc 节点 | compatible/memory-region/name/status 在位 | PASS |
| UFS 禁用 | `/proc/device-tree/soc/ufs@29e00000/status` = `disabled`（v3 修复保持） | PASS |
| systemctl --failed | `0 loaded units listed.` | PASS |
| uname | `6.12.69-gf1b67c293213` | PASS |
| v4 上 mcs_km | insmod RC=0 `/dev/mcs` 508:0；rmmod RC=0；无 kprobe 报错 | PASS |
| v4 上 micad/mcsctl | micad active；mcsctl status RC=0，两实例 Offline（预期） | PASS |

## 5. 板卡当前状态

- v4 内核运行中，CPU7 预留（present/offline，可 PSCI 拉起，衔接阶段5 单实例）；
- 模块未加载，micad 已停止未 enable（干净状态）；
- `/root` 留有：`boot-v4-maxcpus.img(.gz)`、`boot-p3-backup-pre-v4.img`、`mcs_km-tl3572-of-cpu.ko`；
- 回滚路径：v3 镜像（上一级目录）或厂商原版 boot.img，RKDevTool 烧 0x0000a000 或板内 dd。

## 6. 未执行/顺延

- 10 次 insmod/rmmod 冒烟、1000 次模块压测（用户决策本会话不做）；
- 冷启动 10 次 + 24 小时稳定性（此前已顺延）；
- UniProton 镜像启动、IPI/IOCTL 端到端通信（阶段5）；
- 内核成果 Yocto 化：`meta-tl3572-stage3` 建 `linux-tl3572_6.12.bb`（0001 SGI / 0002 DTS /
  0003 of-cpu 补丁 + cmdline config fragment），mcs_km 固化进 rootfs，重出完整 update.img。

## 7. 遗留注意

- 板卡时钟重启后漂移（journald "Time jumped backwards"，疑无 RTC 电池），v3 时代即有，与本次改动无关；
- 厂商 micad 默认实例配置指向 CPU 3 与 rpi4 固件路径，阶段5 需替换为 TL3572 实例配置（CPU7 + 真实固件路径）；
- 阶段7 三实例布局时 maxcpus 需改 3（改 config 重编即可）；
- 串口 COM7 会被本机其他工具占用（Error 5），多工具并用时注意。
