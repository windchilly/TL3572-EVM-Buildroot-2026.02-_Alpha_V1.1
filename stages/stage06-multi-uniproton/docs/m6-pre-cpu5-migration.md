# M6 前置：CPU5 单实例迁移与非连续 CPU 精确保留

> 历史前置报告。M6 双实例已完成，当前部署入口和最终产物以
> `m6-dual-instance-closeout.md`、阶段 README 与 `SHA256SUMS` 为准。此前置阶段的
> boot、模块和单实例 ELF 已从活动目录移除，哈希保留在本文用于追溯。

日期：2026-09-21  
平台：TL3572-EVM / RK3572 / openEuler Embedded 24.03-LTS / Linux 6.12.69 / MICA / UniProton

## 1. 结论

M6 前置阶段结论为 **`COMPLETE`**：单 UniProton 已从 CPU7 迁移到 CPU5，Linux
冷启动仍使用 CPU6/CPU7；非连续 CPU 保留不再依赖 `maxcpus` 或启动后的临时热下线。

本次完成：

- `mcs_reserve_cpus=5` 在 Linux SMP bring-up 前排除 CPU5，同时保留其
  possible/present 状态和 DT CPU 节点；
- `cpu_up()` 拒绝 Linux 后续通过普通 hotplug 上线保留核；
- UniProton 使用逻辑 CPU5、MPIDR `0x101` 和 CPU5 对应的 128 KiB OpenAMP 池；
- Yocto 从干净源码应用补丁并完成 2920 项最终镜像构建；
- 新 boot 冷启动、AutoBoot、SGI8、RPMsg、大包和 1,000 次生命周期回归全部通过。

本次不包含第二实例、SGI9/10、多实例独立内存窗口或 72 小时稳态。

## 2. 实现

### 2.1 Linux CPU 保留

内核补丁 `source/patches/kernel/0002-cpu-reserve-selected-cpus-for-mcs.patch` 新增
早期参数 `mcs_reserve_cpus=<cpulist>`：

1. 用 cpulist 解析逻辑 CPU，拒绝保留 boot CPU0；
2. 从并行和串行 AP bring-up mask 中排除保留核；
3. 保留 `cpu_present_mask`，使 mcs_km 仍能通过 CPU DT 节点取得 MPIDR；
4. 在 `cpu_up()` 中返回 `-EPERM`，防止运行期被 Linux 抢回。

Yocto defconfig 删除 `maxcpus=7`，改为 `mcs_reserve_cpus=5`。内核配方同时断言
新参数存在且不允许遗留任何 `maxcpus=`。

### 2.2 UniProton 与 MICA

UniProton 补丁把 `MCS_CLIENT_CPU_ID` 从 7 改为 5。入口和 LOAD 地址仍为
`0x7c200000`，ELF 大小 589,064 字节；OpenAMP 池由公式自动切换到 CPU5 槽位
`0x7a0a0000`。MICA 配置同步为 `CPU=5`、`AutoBoot=yes`。

## 3. 构建结果

- UniProton `rk3572_mica.elf` 干净重编成功；
- `bitbake tl3572-openeuler-mcs-image`：2920 项任务全部成功，23 项实际执行；
- 内核命令行：`mcs_reserve_cpus=5`，不存在 `maxcpus=`；
- `mcs_km.ko` vermagic：`6.12.69-gf1b67c293213 SMP mod_unload aarch64`；
- rootfs 内 `/etc/mica/tl3572-up0.conf`、ELF 和模块与归档产物哈希一致。

主要产物：

| 产物 | SHA256 |
|---|---|
| `firmware/rk3572-uniproton-cpu5.elf` | `15090a509f769ed6488be14ec1ba58f34305af05d00dd00359218adf36f1d34a` |
| `firmware/boot-tl3572-m6-pre-cpu5.img` | `ebb7d0b13400eb4cb68f8b83f4b3ff374d5b6644594e42e6f79ea076ac970f0a` |
| `firmware/mcs_km.ko` | `c38973bcb1eabfce88669b31ee797980dfa7053891454355d80f440e42048b0a` |
| 内核 Image（远端 deploy） | `33cd1e74681477b504ea322ac0b060b1433f9448eede4560eca2e7bac06ff8c6` |
| rootfs tar.gz（远端 deploy） | `83fab064d9490f5312beab323bbadfc0f5b5c19b2f1671400c0c79939f3dd2a4` |
| rootfs ext4（远端 deploy） | `2b6d742e24c279dc7d09f88d73942d746237a27bfd9c5d11602199f414a181fb` |

rootfs 时间戳文件为
`tl3572-openeuler-mcs-image-tl3572-evm-20260921012455.rootfs.*`。板上未重复写入
4 GiB rootfs，而是部署了与新 rootfs 内逐项同哈希的配置、ELF 和模块；boot 分区
写入新 Yocto boot 后按镜像长度读回，SHA256 一致。

## 4. 实机验收

冷启动结果：

```text
cmdline: ... mcs_reserve_cpus=5
online=0-4,6-7
offline=5
present=0-7
up0  CPU5  Running  rpmsg-tty(/dev/ttyRPMSG0) rpmsg-rpc rpmsg-umt
```

- CPU5 普通 sysfs 上线：写入失败，`Operation not permitted`，状态仍为 offline；
- CPU6/CPU7 均出现 `Booted secondary processor`，继续归 Linux；
- CPU6/CPU7 实机 MIDR 为 `0x411fd090`（part `0xd09`，Cortex-A73）；
- `/proc/interrupts`：GICv2 hwirq 8，名称 `MCS IPI`；
- `systemctl is-active mcs-km-load micad`：均为 active；
- `systemctl --failed`：0；
- 测试结束后 up0 仍为 Running，CPU mask 无变化。

回归结果：

| 项目 | 结果 |
|---|---|
| 100 次 451B + 10 次生命周期冒烟 | `PASS` |
| 10,000 次 451B 顺序回显 | `PASS`，4,780,000B，5.523s |
| 1,000 次 stop/start + 451B echo | `PASS`，741.692s |

完整日志：`tests/m6-pre-runtime-regression.log`，SHA256
`1767fecf6499d095f0b796eddad4b987c03d9a150daf6854c8fbdaeb14513164`。

板卡启动日志仍包含摄像头、传感器、PCIe 等未接外设的既有 BSP 告警；本轮未新增
failed unit、panic、oops 或 MCS/RPMsg 运行错误。

## 5. 回滚点

写入新 boot 前已在板上保存：

- `/root/boot-p3-backup-pre-m6-cpu5.img`，SHA256
  `b3bf02619da09e93fac65feb2228dafb0a10d0116b859703deb1e9c7e3f23c6a`；
- `/root/m6-pre-backup/`：M5 的 CPU7 配置、ELF 和模块。

Stage05 中的 M5 boot、CPU7 ELF 和配置仍是可离板保存的回滚输入。

## 6. M6 下一步

1. 将保留参数扩展为 CPU4/CPU5，并冷启动验证 `online=0-3,6-7`；
2. 把 64 MiB 保留区切为独立共享窗口和 A/B 实例切片，验证所有 vring 边界；
3. 为 UP-A/UP-B 生成独立链接地址、resource table、固件和 MICA 配置；
4. 扩展 mcs_km/micad 的实例资源表及回收路径；
5. 增加并验证 SGI9，SGI10 只预留给 M7；
6. 执行双实例启动顺序、单边启停、并发通信和资源隔离测试。

M5 登记的 72 小时稳态与故障注入继续作为延期补测，不计入本前置阶段，也未在
本轮启动后台长稳任务。
