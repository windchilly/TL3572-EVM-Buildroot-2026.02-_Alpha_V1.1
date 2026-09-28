# M7.0：双实例连续停止的 RPC 日志生命周期修复

日期：2026-09-28。板卡：TL3572-EVM / `192.168.2.141` / openEuler Embedded 24.03 / Linux 6.12.69。用户批准修复并重启回归；本轮只执行一次板卡重启。原 M6 固件、内核和设备树保持不变，未移交工业外设，也没有物理外设收发测试。

## 修复前复现与根因

原 `/usr/bin/micad` SHA-256：`d6722cc43f411c4fb3a00c257d82e3bef74819521f3587ae64e327e752aa6dae`。先启动最终 M7 ELF 的 `up-a-m7`、`up-b-m7`，双路各 100 次 451 B RPMsg 回显及各 2 次单边启停正常；最后执行 `stop up-a-m7`、`stop up-b-m7` 时，第二路停止触发 `SIGABRT`。GDB 在控制线程 LWP 314 捕获：

```text
free → fclose → rpmsg_rpc_service_terminate
     → mica_unregister_all_services → mica_stop → control listener
```

原二进制已剥离符号。结合源码与该次 core 的反汇编，`0x55788c58c8` 是 `fclose` 后的返回位置，`0x55788c899c` 是服务 remove 回调后的返回位置，`0x55788c7e04` 是 `mica_stop` 中注销服务后的返回位置；并非将无符号地址直接当作命名符号。详细现场见 [原版 GDB 记录](micad-abort-gdb-20260928.txt) 和 [本次 core 检查命令](inspect-micad-core.gdb)。这些 ASLR 地址仅适用于该次现场。

MCS `mica/micad/services/rpc/rpc_backend.c` 中两实例共用进程级 `static FILE *fp` 和 `lfd`。旧逻辑每次初始化都重新打开并覆盖这两个全局句柄；每个实例停止都关闭全局句柄，却不清空指针。因此第二次初始化遗失第一份句柄，第一路停止关闭第二份 `FILE *`，第二路又对同一已释放指针执行 `fclose`，导致重复释放。之前“单边停止后马上重启”会重新打开句柄，故不能覆盖最终双停止故障。

旧版崩溃后 systemd 自动重启守护进程，但只恢复了 Linux 进程，不会自动清除远端 CPU 状态。`query_cpu_off.py` 确认 CPU4 OFF、CPU5 非 OFF；经用户允许的一次板卡重启后，CPU4/5 均确认 OFF。Boot ID 从 `eb4206da-7b9e-46b3-ba14-c7575b81d67e` 变为 `808eec59-7c3b-46dc-9b3e-f6dc658c5290`。

现场 core 约 227 MB，仍只留在板卡 `/root/m7-observe-20260928/micad-abort.core`；可能含进程内存，禁止上传公开仓库，Stage07 `.gitignore` 排除了 `*.core`。

## 修改范围与构建

[0003 补丁](../../source/patches/mcs/0003-rpc-shared-log-lifecycle.patch) 仅修改 RPC 后端及其服务注册：

- 共享日志首次使用时打开，增加 `rpc_service_users`；后续实例复用句柄并增加引用。
- 中间实例停止只减引用；最后一个实例停止才关闭 `fp/lfd`，随后设 `fp=NULL`、`lfd=STDOUT_FILENO`；零引用下重复终止直接返回。
- 初始化失败清理已打开的句柄；服务注册失败回退本次引用，初始化错误不再被忽略。

生命周期由现有 micad 控制监听线程串行调用；此补丁保留“进程级 RPC 日志”设计，不宣称实现实例级 RPC 文件隔离。UP1/UP2 的独立启动日志仍通过各自保留内存环及 Linux 读取器提供。本次未启用 `MULTI_WORKERS`，未注入分配失败或文件打开失败。

源码基线为上游 MCS 提交 `5cb49156276be04d54a77a630b8600dcc122fdba`。构建使用独立 `src/mcs-m7`，先应用 M6 的 `0001` 全载荷、`0002` 双 SGI 路由，再应用 `0003`。原 `src/mcs` 与 `meta-tl3572-stage3` 未改动。

复建脚本为 [prepare_m7_mcs.sh](../../build/prepare_m7_mcs.sh) 和 [build_m7_micad.sh](../../build/build_m7_micad.sh)。需要已经构建的 M6 Yocto 依赖组件 `libmetal/openamp/sysfsutils` 及 Arm GNU 14.3 工具链；这不是全新环境的全镜像复建证明。准备脚本在独立的 `mcs-m7-reprocheck` 上重新应用三份补丁并编译成功，目标目录存在时拒绝覆盖。独立构建目录会影响 DWARF 路径，不能仅凭调试版文件哈希不同推断源码不同。

最终交付二进制 [micad-m7-rpc-fix](../../firmware/micad-m7-rpc-fix) SHA-256：`40b7791d55ea58edb92d0119bd985ad560b2d3e1a1eba26ed1aa6566f907d20c`。保留 M6 的 PIE、GNU RELRO、NOW、栈保护；含调试信息，不带主机 RPATH，不重新部署依赖库。完整编译仍有上游 `rpmsg_umt.c:75` 的未使用变量 warning，不能称为零 warning 构建。

新增的独立 [M7 Yocto 附加层](../../source/yocto/meta-tl3572-m7/conf/layer.conf) 已通过元数据解析：`BBFILE_COLLECTIONS` 包含 `tl3572m7`，`SRC_URI` 包含 `0001/0002/0003` 三补丁。用 [预读取配置](../m7-yocto-parse.conf) 配合 `bitbake -r ... -e mcs-linux` 测试，未编辑 M6 的 `bblayers.conf`。尚未用该层重新构建完整镜像/RPM。注意 `-R` 在层发现后读取，不能将其作为新增层已经生效的证据。

## 已验证的初版候选

初版候选 SHA-256 `2e01c092261dec807ce60bccb926aeca9bfc18fcf6fdad101544255fa2c86d9b` 用于定位修复行为，但未作为最终交付构建。

- [小规模测试](rpc-fix-smoke.log)：两种停止顺序各一轮，各 100 回显、各 2 次单边启停，PASS。
- [初版压力测试](rpc-fix-regression.log)：两种停止顺序各 20 轮，交替两种启动顺序；每路在两个测试段各 1000 次 451 B 回显，每段各 10 次单边启停；40 轮 PASS，197.578 s，PID 418 不变、`NRestarts=0`，每轮离线 fd 回到 17。
- GDB 实测 `rpc_service_users` 为 `0→1→2→1→0`，双实例及只剩 UP2 时 `fp=0x7f80000c20`、`lfd=18` 不变；最后停止才变为 `fp=NULL`、`lfd=1`。停止 UP1 后 UP2 单独 100 次回显仍通过。
- [M6 原固件兼容测试](rpc-fix-m6-compatibility.log)：两种停止顺序各一轮，每段双路各 1000 次 451 B 回显、各 2 次单边启停通过；PID 2128 不变、`NRestarts=0`、离线 fd=13。

## 最终 PIE 交付版本回归

最终交付 SHA-256 `40b7791d...907d20c` 已完成单独回归，不能用初版候选的 PASS 替代这个结果。

| 项目 | 最终 PIE 版本实测 |
|---|---|
| UP1→UP2 顺序停止 | 20 轮 PASS；其中 A→B、B→A 启动各 10 轮 |
| UP2→UP1 顺序停止 | 20 轮 PASS；其中 A→B、B→A 启动各 10 轮 |
| 双路并发回显 | 两个测试段，各路各 1000 次，451 B，每路每段收到 478000 B；其余轮各路 5 次回显 |
| 单边停止/重启 | 两个测试段，每段每路各 10 次；另一实例的回显保持正常 |
| 守护进程稳定性 | 40 轮期间 PID 2319 不变、`NRestarts=0`，总耗时 197.683 s |
| RPC 日志 fd | 一路或两路运行时两个日志文件均各开一份；只停第一路不关闭，停最后一路后两份均关闭 |
| 每轮离线 fd | 40 轮均返回基线 17 个；不包含后续 `rm` 路径的无泄漏声明 |
| CPU 状态 | 每次停止相应 CPU 均由 MCS PSCI 查询确认为 OFF；每轮最终 CPU4/5 OFF，无 RPMsg tty 残留 |
| 原 M6 固件兼容 | 4 个启停顺序组合 PASS；两个测试段各路各 1000 回显、各 2 次单边启停，PID 2319 不变，基线 fd=15，耗时 27.461 s |

原始结果分别见 [最终 40 轮日志](rpc-fix-final-pie-regression.log)、[最终句柄观察](rpc-fix-final-pie-probe.log) 及 [最终 M6 兼容日志](rpc-fix-final-pie-m6-compatibility.log)。最终 GDB 再次实测引用数 `0→1→2→1→0`；中间三次 `fp=0x7f94000c20`、`lfd=18` 保持一致，最后变为 `fp=NULL`、`lfd=1`，停止 UP1 后 UP2 单独 100 次回显通过。GDB 的 libthread_db/主机编码 warning 不影响这几个值的读取，没有因此将它们作为完整线程调试能力的证明。

两路保留内存日志的采集服务在压力测试中实际运行并把新 boot 记录写入 `/userdata/uniproton-logs/up-a.log`、`up-b.log`，结束后停止，仍未启用自启动。日志环 Python 读取器 5 项单测再次 PASS；三份交付文件的 `firmware/SHA256SUMS` 均校验通过。

## 仍存在的独立问题与最终部署

本次只修复 RPC 共享日志生命周期。另在临时实例 `create/rm` 清理中观测到两个 `/dev/mcs` fd 残留：删除两份临时 M7 配置后，原 M6 两配置仍存在时，进程 fd 为 15，而全新守护进程仅加载原 M6 配置的基线为 13；残留不是 RPC 日志文件。上游 `baremetal_rproc.c:rproc_init` 每次创建会覆盖全局 `mcs_fd`，`rproc_remove` 只在没有 bare-metal 客户端时关闭当前全局 fd。此项已记录，未扩大本补丁去修改 notifier/MCS fd 生命周期，后续频繁创建/删除测试不能据此宣称无泄漏。最后在 CPU4/5 已确认 OFF 的条件下手动重启守护进程清理，未再次重启板卡。

板卡持久使用 `/usr/libexec/m7/micad`，服务配置 `/etc/systemd/system/micad.service.d/90-m7-rpc-fix.conf` 覆盖 ExecStart；原 `/usr/bin/micad` 及 `10-mcs-km.conf` 未改动，临时 `/run` drop-in 已移除。持久配置先在守护进程重启后实测生效，再执行最终 PIE 和 M6 兼容回归。回退步骤见 [构建说明](../../build/README.md)。

最终仅原 M6 `up-a/up-b` Offline，CPU4/5 均 OFF，`micad` active、无 failed units、管理 ETH1 `eth0` 仍为 `192.168.2.141/24`，日志服务 inactive/disabled。清理重启后的 daemon PID 4028，`/proc/4028/exe` 指向 `/usr/libexec/m7/micad`，fd 恢复基线 13，RPC 引用数为 0、`fp=NULL`、`lfd=1`；重新检查后仍 active，GDB 已脱离。原 M6 ELF SHA-256 仍分别为 `9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8`、`3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4`。

结论：指定的双实例连续停止 `SIGABRT` 故障已修复并完成最终交付版本回归；不意味着所有 MCS 生命周期问题解决，也不意味着 M7.0 外设直驱已经验收。本轮材料仍在本地，尚未提交或推送 GitHub。
