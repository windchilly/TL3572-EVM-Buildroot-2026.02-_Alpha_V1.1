# P3i：真实 MN 周期路径的离线验证（2026-11-02）

结论：**软件周期路径通过；尚无新的可上板 MN 运行候选，也没有新的实板结果。**
本轮不连接板卡、不接管外设、不发送物理帧、不修改开机或正式固件。
最近硬件基线仍为[P3h单次NotActive/关断通过](../powerlink-nmt-p3h-hw-20261023/README.md)，其授权已消耗。

## 发现并修复：可选外部同步通知被误判为故障

[首次离线失败](linux-first.log)在真实NMT进入PreOperational2、首个SoC后返回5；
[调用栈](linux-fault-trace.log)定位到 `dllkevent.c::controlTimeSync()` → `hrestimer_controlExtSyncIrq(TRUE)`。
这不是另一次板端故障。上游正常NMT进程也会发该可选通知；其POSIX/i210/Zynq定时器实现明确允许在不支持外部中断时忽略。
本移植之前却在TRUE时将整个target设为FAULT。旧GsOff/NotActive测试没有覆盖这条路径。

`hrestimer-rk3572.c`仅修正该void可选通知为no-op，不触碰CNTP/PPI30，不冒充外部同步硬件实现。
若显式定义 `TIMER_USE_EXT_SYNC_INT`，构建立即#error；连定义为0也拒绝，避免与上游#ifdef语义冲突。
原生测试验证通知不改变已有timer/截止时间/FAULT；运行脚本实际编译验证0/1两种配置均被拒绝。
没有削弱回调失败、上下文、DMA错误或停止失败的既有保护。

## 真实完整栈，不是手工设置Operational

`test_powerlink_cycle.c`直接链接固定完整上游MN/NMT/OD/PDO/CFM、真实edrvcyclic、RK3572 EDRV和target/hrestimer。
复用原生fixture，只替换RTOS边界、24MHz计时、模拟IRQ/控制器IO和DMA完成；没有伪造NMT事件或CN应答。
只投递SwReset/SwitchOff；默认OD/CDC保留，CN分配全0，没有真实CN/PDO应用配置。

真实状态链：`19 → 29 → 39 → 79 → 21c → 21d → 25d → 26d → 2fd → GsOff`。
分别对应初始化/复位、MN NotActive、PreOperational1/2、ReadyToOperate、Operational及关闭。
模拟时钟下仍经过默认1s NotActive等待和500ms PreOp1等待，没有将等待置零或直接注入Operational。

[最终9场景](linux-cycle-final.log)及[第二次全新构建/累计回归](linux-full-repro.log)：

- normal：10次完整运行/有序关闭，每次至少128个已模拟完成的SoC；总SoC1280、SoA2910、ASnd10、发送完成4200。
- heap_full：相同10轮，1MiB总量减32B头、每块16B对齐+64B开销及128KiB非PLK预留，模型峰636816B、余411728B，live0且回到预留值。
- wrong_owner：非owner拒绝process/stop且不写硬件；恢复合法owner后有序关闭。
- dma_fault / tx_error：真实EDRV错误路径，终态保留资源，不产生错误帧的虚假成功完成或自动清理。
- direct_off：直接SwitchOff会遇到忙缓冲，明确拒绝并保留；不是将该流程写成安全退出成功。
- stop_failure / timer_release_failure：实际周期运行后注入停止失败，保留资源，不释放回调/OD所有者。
- no_completion：揭示下述进度看门狗缺口，仅验证宿主策略原型，**不是现有RTOS保护已实现**。

50us步进、模拟24MHz/IRQ、DMA OWN清除都是测试边界；1ms只是OD值与模拟调度，**不证明实板1ms、抖动、FCS、收发或实时性**。
ETH3/Linux USB对端也未使用，不能将这些计数解释成物理线路抓包或CN互操作。

## 第二个发现：运行态退出必须先停止提交并排空在途发送

[原始全量构建日志](linux-full-build.log)的编译/核心测试完成，但后续native运行在SwitchOff失败，整条命令EXIT134；
[详细停止诊断](linux-stop-trace.log)证实 `edrv_freeTxBuffer()` 返回5，不能释放忙缓冲。
仅将原P3h“NotActive立即SwitchOff”方案延长到Operational是不够的。

[有序停止试验](linux-ordered-stop.log)及最终测试使用：
`edrvcyclic_stopCycle(FALSE) → 有界process/poll排空旧TX → 确认无timer且完成数等于提交数 → SwitchOff/GsOff → stop/exit`。
没有直接擦除EDRV busy状态冒充排空；物理完成仍只是显式模拟。
这目前是测试中的顺序验证，尚未加入UP2 owner或新命令；真实运行退出还须独立回读和未知状态保留。

## 必须补齐的上板前缺口：owner进度看门狗

模拟DMA永久不完成时，旧栈可连续25ms返回OK，发送完成数不前进；库函数返回0不能当作健康证明。
`no_completion`场景如实断言这一事实，然后由**HOST策略原型**将target置FAULT并检查资源保留。
这不是已经实现的RTOS watchdog，更不是可抢占卡死栈调用的硬件看门狗。
因此本轮**不增加PLK run命令、不生成累计ELF、不准备板端runner或询问发帧授权**。

后续先将有界时间/周期数、owner与NMT合法状态、发送完成进展、定时器丢周期/迟到、硬件错误、
有序停止/排空和首错证据接入独立默认关闭的UP2运行诊断；离线故障注入和最终ELF预算通过后才另开硬件授权窗口。
真正CN发现/配置、PDO/SDO、应用看门狗、伺服/IO业务和长稳/实时验收仍未完成。

## 构建、回归与复现

服务器Docker `dev_openeuler`，本轮独立根 `/home/openeuler/build/powerlink-cycle-p3i-20261102`。
`stage/`为精确工作输入；`software`与`software-repro`都从固定归档完整编译native+AArch64，未复制预构建核心。
[9个AArch64产物比较](repro.json)逐字节一致；native也全新编译并运行回归，但未将native库纳入此逐字节比较，不包含或声称构建了runtime/ELF。
最初两次探索明确复用P3h software-repro定位旧行为，不作为这两次全新构建。
首次全量命令虽最终因停止顺序失败，但编译产物已完整形成；修正的是测试顺序，生产库在两根一致。

[Windows208项](windows.log)、Linux208项、原P3h NMT27+邮箱4及旧P3f/P3e/P3d/P3c/P3b/P0–P2累计原生回归通过。
5个新Python用例检查可选通知/配置拒绝、真实状态推进、无板端入口及循环边界；不是以字符串测试代替真实原生运行。
固定上游仍有旧编译告警，完整日志保留，不能称无告警构建或生产就绪。

先恢复[固定源码/SDK/Docker](../../../../repro-inputs/rk3572/README.md)，在stage07目录运行：

```bash
export TOOLCHAIN_PATH=/path/to/toolchain-14.3
POWERLINK_BUILD_ROOT=/tmp/p3i-software bash build/build_m7_powerlink_cycle.sh
POWERLINK_BUILD_ROOT=/tmp/p3i-software bash tests/run_powerlink_nmt_probe_native.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

构建根必须不存在，脚本拒绝覆盖。旧清单、旧候选与P3h硬件证据保持原记录；不要拿新源码的可选hook语义冒充旧P3h ELF已经包含修复。
新 `SHA256SUMS`继承完整源码与旧证据；`verify_powerlink_cycle_checkpoint.py`只做离线归档/208测试/真实解包补丁校验，不连接板卡。
首次GitHub清单恢复漏列新增 `run_powerlink_cycle_native.sh`，精简检出208项中1项缺文件；[原始失败](github-first-failed.log)保留。
脚本原已提交，仅补清单/依赖断言，并在原5项Python用例中加入清单覆盖回归；最终另建全新检出复核，不修改运行源码或伪造通过日志。
GitHub/服务器后验日志不纳入自身清单；同步状态及GitHub新检出验证以最终报告为准。
