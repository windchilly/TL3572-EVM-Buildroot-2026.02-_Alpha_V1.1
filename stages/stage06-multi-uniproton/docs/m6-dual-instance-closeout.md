# M6 双 UniProton 多实例收口报告

日期：2026-09-21  
平台：TL3572-EVM / RK3572 / openEuler Embedded 24.03-LTS / Linux 6.12.69 / MICA / UniProton

## 1. 结论

M6 当前功能与构建范围结论为 **`COMPLETE`**。UP-A/UP-B 已分别运行于 CPU4/CPU5，
Linux 继续使用 CPU0～3、CPU6、CPU7；双实例拥有独立通知中断和内存资源，可按
任意顺序启动，并能在另一实例有序停启时保持 RPMsg 通信。

本轮不实现主备、状态同步或 2oo3 表决。panic、死循环、非法访问等破坏性故障注入
留到阶段10；M5 登记的 72 小时稳态按用户决定延期补测，不作为本轮退出条件。

## 2. 最终资源分配

```text
Linux: CPU0-3, CPU6-7
UP-A : CPU4 / MPIDR 0x100 / SGI8
UP-B : CPU5 / MPIDR 0x101 / SGI9
```

| 资源 | UP-A | UP-B |
|---|---|---|
| 配置 | `/etc/mica/tl3572-up-a.conf` | `/etc/mica/tl3572-up-b.conf` |
| AutoBoot | `no` | `no` |
| 固件 | `rk3572-uniproton-up-a.elf` | `rk3572-uniproton-up-b.elf` |
| ELF 入口/LOAD | `0x7b200000` | `0x7c200000` |
| MMU 区 | `0x7ba00000` | `0x7ca00000` |
| OpenAMP 池 | `0x7a080000..0x7a09ffff` | `0x7a0a0000..0x7a0bffff` |
| notify SGI | 8 | 9 |

两个 `micad` 进程映射的物理共享池经 `/proc/<pid>/maps` 核对互不重叠。每个共享池
大小均为 128 KiB；镜像区、MMU 区、resource table 和 vring 地址由实例构建参数生成。

## 3. 实现内容

### 3.1 CPU 保留与内核 SGI

- `mcs_reserve_cpus=4-5` 在 SMP bring-up 前排除 CPU4/CPU5，并保留 possible/present；
- arm64 为 MCS 分配并导出两个索引化中断，Linux 原生 IPI 使用 SGI0～7，MCS 使用
  SGI8/SGI9；
- `mcs_km` 分别注册 `MCS IPI8` 和 `MCS IPI9`，发送路径按目标实例选择 SGI；
- MCS 用户态轮询把 SGI8/SGI9 分别映射为不同事件位，只唤醒对应 client。

### 3.2 GICv2 双实例根因修复

初版双实例中，任意实例单独运行正常，但启动第二实例后两路 RPMsg 同时失效。物理
映射核对证明不是共享内存重叠。根因是 CPU4/CPU5 被 Linux 预留后不会执行
`gic_cpu_init()`，`gic_cpu_map[4]` 和 `[5]` 均保留未解析掩码 `0x30`；因此给任一
保留核发送 SGI 都会同时命中 CPU4 和 CPU5。

最终补丁在 `gic_smp_init()` 中显式设置 CPU4/CPU5 的 GICv2 target map 为各自 bit。
修复后 SGI8 仅到 CPU4、SGI9 仅到 CPU5，双实例并发与单边停启恢复正常。

### 3.3 UniProton 参数化

同一套源码通过 CMake 参数生成两个实例：

- `MCS_CLIENT_CPU_ID`：4 / 5；
- `MCS_NOTIFY_SGI_ID`：8 / 9；
- `MCS_IMAGE_ADDR`：`0x7b200000` / `0x7c200000`；
- `MCS_MMU_ADDR`：`0x7ba00000` / `0x7ca00000`。

入口模板、MMU 映射和 OpenAMP 地址均由这些参数派生，复建入口为
`source/overlay/uniproton/demos/rk3572_mica/build/build_m6_instances.sh`。

## 4. 构建结果

最终补丁基于 BitBake 实际前置源码刷新后：

- `do_patch` 精确应用，无 fuzz；
- `bitbake tl3572-openeuler-mcs-image`：2920 项任务全部成功；
- 最终构建无 warning；
- boot 分区按 40,647,168 字节回读，SHA256 与归档镜像一致；
- 板上 `mcs_km.ko`、`micad` 与归档产物 SHA256 一致。

| 最终产物 | 大小 | SHA256 |
|---|---:|---|
| `firmware/boot-tl3572-m6-dual.img` | 40,647,168 | `a6a050cd9aa335516907ca79c290084e9585c03c3d53a660d262c8789515a436` |
| `firmware/mcs_km.ko` | 98,472 | `85818cc30f503f3fb84c548ebac2ebce76adb68d57d5e6fea63e74d0a1baff6c` |
| `firmware/micad` | 114,368 | `d6722cc43f411c4fb3a00c257d82e3bef74819521f3587ae64e327e752aa6dae` |
| `firmware/rk3572-uniproton-up-a.elf` | 589,040 | `9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8` |
| `firmware/rk3572-uniproton-up-b.elf` | 589,040 | `3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4` |

## 5. 实机验收

最终镜像冷启动基线：

```text
cmdline: ... mcs_reserve_cpus=4-5
online=0-3,6-7
offline=4-5
up-a CPU4 Offline
up-b CPU5 Offline
systemctl --failed: empty
```

执行结果：

| 测试 | 结果 |
|---|---|
| A 单实例，10×451B | `PASS` |
| A→B，双路各 1,000×451B 并发 | `PASS`，0.549s / 0.558s |
| A→B，单边停启 50 轮/实例 | `PASS`，147.793s |
| 重启后 B 单实例，10×451B | `PASS` |
| B→A，双路各 1,000×451B 并发 | `PASS`，0.496s / 0.492s |
| B→A，单边停启 20 轮/实例 | `PASS`，59.221s |
| 最终零警告镜像，双路各 1,000×451B | `PASS`，0.478s / 0.487s |

正序/逆序启动时 `/dev/ttyRPMSG0` 与 `/dev/ttyRPMSG1` 会随注册顺序交换，测试按
client 与设备的实际映射执行，两种顺序均通过。50 轮隔离后中断计数为
`MCS IPI8=1212`、`MCS IPI9=1202`，`Err: 0`，两个实例仍为 `Running`。

## 6. 复现与回滚

1. 以 Stage05 最终 UniProton 源码为基线，覆盖 `source/overlay/uniproton/`；
2. 按 `source/patches/kernel/` 顺序应用三个内核补丁；
3. 按 `source/patches/mcs/` 顺序应用两个 MCS 补丁，并部署 `source/mcs-km/mcs_km.c`；
4. 将 `yocto/` 文件同步到 `meta-tl3572-stage3` 对应 recipes/files；
5. 运行 UniProton 双实例脚本，再运行 `build/rebuild-m6-dual-image.sh`；
6. 用 `SHA256SUMS` 校验归档，并按镜像长度校验 boot 分区回读结果。

板上保留的主要回滚点：

- `/root/boot-p3-backup-pre-m6-dual.img`；
- `/root/m6-dual-predeploy-20260921/`；
- Stage05 最终固件与 Stage06 CPU5 前置报告。

## 7. 下一步

进入 M7 三实例：把 UP-A/B/C 调整到 CPU3/CPU4/CPU5，Linux 使用 CPU0～2、CPU6、
CPU7；新增 SGI10、第三组共享池/镜像/MMU 地址和 UP-C 配置。先保持手动启动，完成
六种启动顺序、三路并发和任一实例有序停启隔离后，再决定是否启用自动编排。
