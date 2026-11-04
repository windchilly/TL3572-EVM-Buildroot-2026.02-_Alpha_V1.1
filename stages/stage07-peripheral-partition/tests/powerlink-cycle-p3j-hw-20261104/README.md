# P3j：一次有界周期实测窗口（2026-11-04）

结论：**唯一一次有界MN周期运行通过；原runner清理验收失败，现场保留，整轮不是PASS。**
已定位为TCB任务入口解码错误，新增离线检查已验证实际三路栈合格；未重新运行周期或自动继续清理。

用户新确认：“隔离回环仍在，允许一次 P3j 有界周期测试”。
仅固定候选 `4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`，
临时移交 ETH2/CNTP，单次 reset→Operational（100ms 或256次TX完成先到，总软件预算8s）→排空→SwitchOff。
只在停止及真实堆证明完整后归还Linux；可能发有限POWERLINK协议帧。
不含持续运行、真实CN/执行器、CAN/串口、专用测试帧、正式固件/开机修改、自动重启或异常重试。
隔离ETH2↔ETH3不改变，不打开COM7。未知状态保留现场。

主机编排源码为本目录 `board_window.py`；实际runner/19项输入见
[固定软件准备](../powerlink-cycle-p3j-runner-20261104/README.md)。
不得覆盖或删除ATTEMPTED来重投。本窗口已经消耗；后续只允许新授权的资源归还，不再start/stop或发新周期。

## 实际执行

执行前源码提交 `2d36c3a0c9188cb1ccbdfe2430a607ff55364cfc`。
[预检](preflight.log)匹配固定内核、原固件/hold/日志器SHA，CPU4/5 OFF、原两实例Offline、隔离两口Linux100Full/ANon。
本次boot=`63986874-c4a0-4c1a-95b0-a92deb7f3bae`，不是10月23日旧boot；micad PID329/NRestarts0/active。
[19项实际上传读回回执](board-input-sha256.json)逐项匹配固定软件准备，候选未改/未重编。
[永久ATTEMPTED](ATTEMPTED.txt)、[完整运行日志](board-test.log)和[原始板端结果](board-result.json)保留，不覆盖。

只投递一次 `PLK cycle-probe`，reset/off各1、stopCycle一次、rc0/clean1/stage9/context1/trips0。
实际自然到Operational `0x2fd`，最终COLD/GsOff；598738次process/14events，runLoops36641/drain374/offLoops1。
完成376次TX，Operational前176次、停止调度时376次，停止时pending0，最大pending1；收尾期间未增加TX。
运行期真实CNTP/PPI30中断376/回调376，无丢周期，统计最大定时器迟到458ticks≈19.1µs。
计数器总跨度约4.074s，包含PHY准备；runCounter到endCounter约102.6ms，含排空/退出。
没有独立stopCounter，不能把102.6ms当成精确Operational运行时长；实际固定生产函数以100ms或256完成先到收尾，本次运行增加200TX。
这些是一次隔离开发测试统计，不是最坏时延、长期实时性、真实CN/PDO/SDO或生产验收。

RX delivered/rxErrors/txErrors/fatal均0，允许的RX dropped4如实记录；没有独立全线抓包，不能声称线路绝对零背景帧。
ETH2由UP2轮询直驱，100Half/ANoff；hold只是共享电源/root clock，不代理数据。
原有CAN/串口测试未执行，正式M6/M7/DT/kernel/开机未改；没有打开COM7或重启。

## 首次停止证明与清理失败

原runner先完整验证1504+608缓存成功，再stop新临时client**一次**；独立CPU4/5 OFF后读取真实堆和TCB。
随后错误地要求PLKowner也从TCB偏移48找到Worker，报告 `actual RPMsg/PLKowner stacks changed/missing`。
`BOARD_EXIT_CODE=1`、`passed=false`、`cleanup=false`、`private_stopped=null`均保留，不改写成原runner成功。
在此失败后没有第二次stop、rm/rebind/rmmod/自动重启/重试。

[只读保留现场清点](retained-readonly.log)前后再次独立确认CPU4/5 OFF，读取小范围私有DRAM而不是控制器MMIO。
[原始1504B](private-snapshot.hex)、[原始608B](private-cycle.hex)及[实际TCB/堆数据](retained-private.json)均存档。
MAC/TX/RX/DMA/IRQ停止六回读均0，ETH/timer lease0，CNTP_CTL2/PPI30静默，OS虚拟tick/GIC相关字段保持；异常cause/ELR/ESR0。
真实FSC：total1048544，初始used/peak37520，停止后used38584/peak543648，峰值余504896>256KiB，used差1064。
used差含RTOS/RPMsg背景分配，单轮不能证明无泄漏/无碎片。

当前保留状态：CPU4/5 OFF，新临时client Offline但未rm，ETH2仍从Linux解绑，hold仍加载；ETH3为100Half/linkyes。
管理ETH1（Linux eth0）地址路由正常，micad PID329/NRestarts0/active、CAN全DOWN、failed服务0、taint4096无Oops128，原M6两固件SHA不变。
已经另问“核验后仅清理并归还Linux”的新许可；未获新回复前不继续资源变更。本页保留状态仅对应这次实际清点时间，不暗示后续状态未变。

## TCB校验器根因与最小修复

真实 `TagTskCb.taskEntry` 在偏移32，`args[0]`在偏移48。
PLKowner直接由 `PRT_TaskCreate` 创建：TCB[6].taskEntry=Worker、args0=0、静态ownerStack=32768。
RPMsg线程由pthread创建：TCB[8/9].taskEntry=OsPthreadWrapper、args0=业务函数，栈各4096。
旧reader沿用了RPMsg的参数位置识别PLKowner；旧mock又将Worker人工填进args0，所以未发现真实创建路径差异。
原先并非“页表/任务栈变小”或固件失效，而是新增校验器的错误假设。

新增 `board/powerlink_cycle_p3j_tcb_checks.py`，分别校验直接taskEntry与pthread包装器/args0，还检查静态owner栈基址、任务ID、SP范围及重复记录。
历史reader/runner、固定ELF和已上传19项均不修改，不放宽栈门槛。
[实际RTOS头文件编译1](tcb-abi.json)/[编译2](tcb-abi-final.json)字节一致，native/AArch64均为 `[800,16,20,24,32,48]`。
使用候选对应累计树实际头/配置及pthread_create源，记录SHA；libRK3572 SHA与原候选ABI报告相同，不是手写替代TCB或重新编译固件。
原始 `threads_raw.entry` 字段是首次检查按偏移48记录的值，**不是**真实taskEntry；新校验只从原始80B raw_hex按已编译布局解析。

[Windows273项](windows.log)/[Linux273项](linux-final.log)通过，旧263+新10；包括实际TCB重现旧reader误报、双类型入口、假args/错误wrapper/错误栈/SP/重复任务拒绝。
新增独立验证器仅复核已归档证据，不连接板卡，不代表已经完成Linux归还。
构建服务器read-only查找时缺rg、初次路径不存在日志保留；有效头文件/创建函数见tcb-definition/tcb-includes和实际ABI报告，不把前两次查找当成ABI证据。

## 离线复核与归档

在仓库根运行（绝不重新执行硬件）：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cycle_p3j_hw_checkpoint.py \
  /tmp/new-p3j-hw-prepared --expected-commit <当前检出提交>
```

新SHA清单继承全部727项软件准备路径，加入本次实际运行、失败、只读证据和TCB校验源码；旧清单不重生成。
仅滚动memory/stage索引更新，既有源码/固定ELF/证据SHA保持；历史文档完整版本在原提交使用。
GitHub/服务器后验日志不含自身哈希，实际同步状态以最终报告为准。
按karpathy-guidelines只新增独立校验及实际回归，不修改固件或覆盖失败，也不把软件修正当作资源清理授权。
