# P3j 单次周期板端工具准备（2026-11-04）

独立工具软件准备/离线回归通过；固定 2026-11-02 P3j 候选不变，尚未连接或部署板卡。
本目录不是硬件 PASS，旧 P3h 一次授权已使用，不能复用。

新增独立 runner、608B 解码器、真实 FSC 门槛和停止前/停核后交叉检查。
新窗口 `/root/m7-powerlink-cycle-p3j-20261104`，新 client `up-b-m7-plk-cycle-p3j`。
候选 SHA256：`4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`。
`AutoBoot=no`，只允许一个 `PLK cycle-probe`；模糊写入后仅观察，不重投。

固件 BSS 的一次性标记只在**本次 UP2 加载期间**有效，重新加载会清零。
新 runner 在任何移交前独占创建并 fsync 永久 `ATTEMPTED`，不得删除或覆盖来重测。
这不是防止管理员主动绕过脚本的安全边界，也不能代替新的隔离网络授权。

## 本次完成与保护边界

只允许新的 `--confirm-isolated-p3j-cycle` 和固定 SHA；它是脚本门槛，不是硬件授权本身。
命令白名单仅 `M7 status`、`PLK status`、`PLK cycle-probe`、`PLK cycle-status`。
19 项精确输入见 [runtime-inputs.json](runtime-inputs.json)，另列既有 hold 模块和系统日志读取器 SHA。
本目录没有板端上传回执/运行结果，不可把 `prepared_only` 当成已部署。

固定候选实际流程见 [P3j 构建报告](../powerlink-cycle-p3j-20261102/README.md)：
reset 自然进入 Operational → 100ms 或 256 次 TX 完成先到 → 停调度/排空 → 一次 SwitchOff → stop/exit。
完整 OD/40RX/40TX/254 映射保留，CN 分配全零；可能发送有限 POWERLINK 协议帧，不发送专用测试帧或 CAN/UART。
8s/4M 次总预算及其他进度门槛只在调用返回后检查，不能抢占卡死调用，不是硬件 watchdog 或实时验收。

成功判据不沿用旧 NMT 的零 TX/零 IRQ；新解码器要求完成 TX、IRQ/回调、自然 Operational、无错误/丢周期、pending 排空、一次 stopCycle/off、最终 COLD。
公开结果成功后，**先**读取稳定私有 1504B+608B 完整结果校验再 stop 新 client 一次。
独立确认 CPU4/5 OFF，读异常/lease、FSC 和实际 TCB，再确认 OFF；跨 OFF 两份结果逐字节一致才允许 rm/rebind/卸载 hold。
已停核但证明失败同样保留资源，绝不第二次 stop、自动 CPU_OFF/恢复/重启。

实际 TTY/listen 栈均要求4096，固定 ELF 的 `Worker`/PLKowner 要求32768且任务 ID 与结果一致。
M6 TCB stride800/异常520内部偏移仍是固定 ABI，不是自动发现或全路径栈峰值测量。
真实 FSC 要求池1MiB、总量1048544、COLD可用至少767888、实际峰值余量至少256KiB。
used差包含RPMsg/RTOS背景分配，仅记录，不作为严格无泄漏/碎片保证。
结果没有单独 reset/drain/stopCounter；离线只检查可证的必要界限，具体阶段期限由固定生产函数执行，不能声称缓存可重建全部期限。

## 实际验证

[Windows最终263项](windows-final.log)、[Linux最终263项](linux-final-fixed.log)通过，旧215+新48。
新增覆盖错误候选/ABI/未发布或失败结果、时钟及流量预算、真实堆阈值、读前后OFF顺序、实际线程栈、永久单次/短写/模糊ACK、首次stop前完整证明、停核后失配、恢复漂移保留hold。
完整系统/命令/DRAM边界均为mock，无板卡IO。

两次 [实际编译布局1](p3j-abi.json)/[布局2](p3j-abi-final.json)字节一致：native GCC 与 AArch64 的23项缓存布局、10项608B周期布局、源头提取FSC头32B/uintptr8一致。
14项真实ELF私有符号匹配，记录实际RTOS头/源/libRK3572 SHA；没有执行实板FSC分配器。

[原生运行及解码](linux-capture.log)、[完整最终回归](linux-final-fixed.log)：
P3j生产guard18+owner4、P3i9、原NMT27+owner4通过。原生只模拟时间/IRQ/RTOS/DMA完成等硬件边界。
新capture工具采集生产函数实际608B：[normal](normal-host.bin)/[受限堆](heap-full-host.bin)，均32142 process、374 TX完成、14 events，解码器通过。
这两项通用mailbox是按实际结果**合成**，不是实际owner/RPMsg/实板停核证据。
重复采集608B字节相同，首次全量ABI输出与第二次相同。

本轮仅重编harness/生产guard和ABI夹具，**明确复用**11月2日 `software-repro` 核心库；没有重建完整核心或累计ELF。
首次 [capture编译失败](linux-first.log)为历史harness内部main宏冲突，去掉新夹具不必要的main重命名后通过，旧harness不改。
[第一次最终命令](linux-final.log)在263项/P3j/P3i通过后因附加NMT脚本名称写错整体EXIT127，日志保留；使用实际文件后最终全部通过，不覆盖失败。

## 复现、归档与下一步

在固定 [源码/SDK/Docker](../../../../repro-inputs/rk3572/README.md)恢复后，先按原P3j报告构建 `software-repro` 和累计树，再运行（不部署）：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/audit_powerlink_cycle_p3j_abi.py \
  tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf \
  /path/to/UniProton-repro /path/to/toolchain-14.3 /tmp/p3j-abi.json
POWERLINK_BUILD_ROOT=/path/to/software-repro POWERLINK_CAPTURE_ROOT=/tmp/new-p3j-capture \
  bash tests/run_powerlink_cycle_p3j_capture.sh
POWERLINK_BUILD_ROOT=/path/to/software-repro bash tests/run_powerlink_cycle_probe_native.sh
```

`POWERLINK_CAPTURE_ROOT`必须不存在。ABI报告应与本目录布局/符号一致；路径相关的库SHA取决于使用相同固定累计树，不应把任意重建库当成本次实际候选库。
本轮服务器根 `/home/openeuler/build/powerlink-cycle-p3j-runner-20261104`，历史树/窗口不动。
新清单继承672项历史路径，保留旧清单；只更新滚动memory/stage索引，旧源码/候选/证据仍按旧SHA核验。
历史清单完整版本应在原源码提交 `0dad284` 使用，新清单核验当前文档版本。GitHub/服务器后验日志不包含自身哈希。

最近实板结果仍2026-10-23 P3h单次NotActive测试，不能称已实板跑通Operational/CN/PDO/SDO/1ms实时性。
归档门槛通过后，另问 **ETH2↔ETH3仍隔离 + 新P3j单次有限周期/协议帧** 授权，再建独立硬件证据。
无新回复前不SSH/上传板卡，不接管ETH2/CNTP、不发帧、不打开COM7；正式M6/M7固件、DT/开机不变，CAN/UART不发送持续有效。
工具设计受本轮 karpathy-guidelines 约束：不改固定固件/历史runner，分别验证新入口的拒绝路径与可证明边界。
