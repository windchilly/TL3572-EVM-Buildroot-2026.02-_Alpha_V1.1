# TL3572 openEuler Embedded 阶段2归档（2026-09-15）

本目录是阶段2（openEuler rootfs 在 TL3572 启动）的唯一本地归档。
背景、验收标准与实机验证记录见根目录《TL3572_openEuler_MICA_UniProton_2oo3_完整移植路径.md》第5节。

## 可烧录产物

- `rootfs-openeuler-tl3572-mcsctl.ext4.gz` — 阶段2最终合并修正镜像（含网络修复 + mcsctl 软链接修复）
  - 解压后逻辑大小 4294967296 bytes，解压内容 SHA256 `75fb4ad8db3432b4258c4b5231cc5ffd0ff77c30d0ef931953afa74df9e831f6`（SHA256SUMS 第1行）
  - 只能烧写 rootfs 分区（RKDevTool 地址 0x0007a000），不得覆盖 boot / uboot / Loader
  - 原始 4 GiB ext4（openeuler-image-qemu-aarch64-20260915082322.rootfs.ext4）已删除：经哈希验证与本 gz 解压内容逐字节一致，需要时 `gzip -dc` 即可恢复；远程构建机 `/home/openeuler/build/tl3572-2oo3/build/build-rootfs/tmp/deploy/images/qemu-aarch64/` 仍保留同一文件
- `SHA256SUMS` — 7 项已于 2026-09-15 逐一验证一致
- `rootfs.manifest` / `compile.yaml` / `build.log` / `e2fsck.txt` / `mcsctl.bbappend` — 构建、配置与修复记录

## logs/ — 首次烧录实机验证证据

- `boot-log-rootfs-stage2-115200-retry.txt` — 唯一有效的完整启动串口记录（DDR 训练 → U-Boot → 内核 → systemd → login）
  SHA256 `d421eacb1ebd99a4b6cb974c0090a55365c6b1cc2245c858c3b281bad4eb301f`
- `flash-rootfs-stage2-final.log` — RKDevTool 成功烧录记录（0x7a000）
  SHA256 `446a422c033ec7908459521d225a788e213d8ed8c0cee2be1eaef40fc1370746`
- 烧录所用 RKDevTool 工具链位于 `C:\Users\limew\Documents\Codex\2026-09-11\i-tl3572-evm-buildroot-2026-02\stage2\tools\rkdevtool-0.15.0-extracted\`（flash 日志中引用）

## 2026-09-15 整合记录

原 `TL3572_openEuler_stage2_20260915\`（首次构建/烧录目录）已整体删除，其中：

- 旧镜像 `rootfs-openeuler-tl3572.ext4`（4 GiB）、`-flash-3584MiB` 变体（3.5 GiB）、`.gz`（110 MB）及其校验文件 — 已被本目录最终镜像取代（旧镜像存在 eth0 双 IP 与 mcsctl 软链接缺失问题，见移植路径文档 5.7）
- 首次构建的 `build.log`、与最终版逐字节相同的 `compile.yaml` / `rootfs.manifest`（哈希比对确认重复）
- 6 个 `*first4MiB*.bin` 烧录诊断转储（24 MB）
- 2 个无效串口采集（1.5 MB / 307 KB，非空字节仅 83 / 82，仅含 BootROM 阶段 `rboot` 输出）
- 2 个空文件、1 个中止的烧录日志（276 B）

回滚板卡始终使用完整厂商 `update.img`（Loader 模式），与本归档无关。
