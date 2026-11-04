# P3j runner-v2：一次实板自动闭环（2026-11-04）

结论：**本次唯一实板周期及新版自动停核证明/归还 Linux 全流程 PASS。**
不是将旧失败结果改成成功，也不是将上次“周期成功 + 另获许可归还”拼成一次自动通过。
本次获新的 ETH2↔ETH3 板上隔离回环/一次 v2 闭环许可；现已用完，不重跑或重用该窗口。

## 固定输入和执行

- 执行来源提交 `3b07cd341d2874f4e6dba6259ff88e09004e27ae`；[22项上传读回回执](board-input-sha256.json)与[已准备清单](../powerlink-cycle-p3j-v2-20261104/runtime-inputs.json)逐项 bytes/SHA 一致。
- 沿用原 P3j 累计 ELF：`4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`，1220888B；没有重建或更改正式固件、DT、内核、开机配置。
- 独立 root `/root/m7-powerlink-cycle-p3j-v2-20261104` / client `up-b-m7-plk-cycle-p3j-v2`，AutoBoot=no；[主机永久标记](HOST_EXECUTION_ATTEMPTED.json)和[板端永久标记](ATTEMPTED.txt)保留，不覆盖结果。
- [board_window.py](board_window.py)分 preflight/upload/run/postflight；唯一 run 在 SSH 调用前先创建本地主机标记，远端日志 noclobber，runner 在资源移交前创建板端标记。任何通信/状态不明都不重投。
- [原始执行日志](board-test.log)、[完整结果](board-result.json)、[SSH退出码](ssh-execution.log)保留；实际 `passed=true/cleanup=true/submitted=true/error=null/BOARD_EXIT_CODE=0`。

## 本次观测

单次 reset → 自然达到 Operational `0x2fd` → 停周期调度一次 → 排空 → SwitchOff/GsOff → COLD。
reset/off=1/1、rc=0、clean=1、stage=9、context=1、watchdogTrips=0；公开结果与私有1504+608缓存一致。

| 项目 | 本次实际值 |
| --- | --- |
| process / events | 597790 / 14 |
| run / drain / off process | 36578 / 372 / 1 |
| TX完成 / 进入Op前TX / 停调度时TX | 376 / 176 / 376 |
| pendingAtStop / maxPending | 0 / 1 |
| 定时器IRQ / 回调 / skippedPeriods | 376 / 376 / 0 |
| 最大记录迟到 | 3950 ticks，24MHz下约164.6μs |
| RX交付 / RX错误 / TX错误 / fatal / dropped | 0 / 0 / 0 / 0 / 4 |
| 真实FSC总量 / COLD used及peak | 1048544B / 38584B |
| 停后used / 峰值 / 峰值余量 | 38584B / 543648B / 504896B |
| owner / TTY / listen 分配栈 | 32768B / 4096B / 4096B |

总 counter 跨度约3.979s，包含 PHY/栈准备；runCounter至endCounter约102.582ms，含排空/退出，不是精确Operational时长。
保持原100ms或256次TX完成先到、8s/4M总软件预算和≤1024提交；不增加时长或开放持续run。
164.6μs只是这一次记录的最大迟到，不是最坏实时性承诺；与前次不同不隐瞒。
FSC used差0仅为两个观测点相同，不是严格无泄漏或碎片证明；没有读取RTOS栈正文，不声称实测栈水位。
本轮无真实CN，RX交付0；376TX为驱动完成证据，不是CN应答/PDO收发或对端线侧抓包证明。dropped=4原样保留，不声称网络丢包0。

## 自动停核和归还

公开完成及完整live私有证明通过后，仅stop新client一次。
独立CPU4/5 OFF前后读取1504+608/真实FSC/17项80B TCB前缀；跨OFF两份结果逐字节一致。
直接任务 taskEntry@32 与 pthread wrapper@32/args0@48 分别检查通过，PLKowner id=6，三路栈大小合格。
ETH lease=0、异常cause/ELR/ESR=0、MAC/DMA停止六回读为0，CNTP_CTL=2、PPI30静默及timer armed=0。
全部证据合格后才rm临时实例注册、重绑Linux ETH2、eth1 up、等待两端100Full/ANon/linkyes，最后卸hold；不是强制恢复。

[前检](preflight.json)与[独立后检](postflight.json)完整相同，四组只读原始日志另存；[SFTP只读补采](collect_files.py)得到[52文件SHA](post-file-sha256.json)：正式6文件、原窗口19项/标记/失败结果/归还结果、新22项及新结果/标记均未改变。
最终boot `63986874-c4a0-4c1a-95b0-a92deb7f3bae`、micad PID329/NRestarts0/active、CPU online0-3,6-7/物理CPU4、5OFF、仅原up-a/up-b Offline。
ETH2/ETH3均归Linux100Mb/s Full/ANon/linkyes，无RPMsg端点或hold；管理eth0的192.168.2.141/24及路由、工控寄存器和Linux驱动不变。
CAN0..3 DOWN、failed services=0、taint4096无Oops128；没有CAN/串口/专用测试帧、COM7访问、重启、第二次stop或周期重试。
Linux重绑后的正常协商/后台网络不等同于UP2继续发送测试帧。

## 离线复核、交付和剩余边界

新增7项实际证据及篡改拒绝回归，Windows全套[312项通过](windows.log)。
新校验器重新解码1504+608和实际17项TCB，复核22项回执/永久标记/独立OFF前后检/52文件不变；没有mock本次证据，也不会连接板卡。
原305项、原runner/reader/TCB证明/固件、历史失败与独立归还记录均保持；按照karpathy-guidelines仅接入最小修复，不混改历史。
在仓库根执行下列命令仅验证归档、312项测试和固定1355个上游源码文件及真实补丁，不会执行板端脚本：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cycle_p3j_v2_hw_checkpoint.py \
  /tmp/new-p3j-v2-hw-prepared --expected-commit <当前检出提交>
```

新SHA清单继承上一软件版全部797项，旧清单不重生成，仅滚动memory/stage索引更新。
GitHub全新检出与构建服务器 `/home/openeuler/build/powerlink-cycle-p3j-v2-hw-20261104/delivery` 的后验日志单独归档；实际核验结果以最终报告及这两个日志为准。
本轮无核心或累计ELF重编；服务器复核是Linux离线证据/回归和精确交付，不冒充重新构建整个SDK。

当前只验收**无CN的单次有界MN诊断及自动安全退出**。真实CN/PDO/SDO、持续MN、长稳和最坏周期抖动仍未验收。
下一步需先明确隔离CN的型号/固件、XDD或CDC、NodeID、PDO映射和目标周期，再准备互操作；新接线/设备或新硬件窗口须另确认，不能复用本次许可。
