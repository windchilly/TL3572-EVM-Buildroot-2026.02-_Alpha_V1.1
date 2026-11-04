# P3j runner-v2：正确线程证明与自动归还软件闭环（2026-11-04）

结论：**runner-v2软件闭环/回放/回归通过；本版未上板。**
本轮不连接板卡/COM7，不接管ETH2/CNTP，不发送或重跑周期，不重启。
固定P3j候选4b485415...保持；v2表示板端工具版本，不是新固件或更长运行预算。
新root `/root/m7-powerlink-cycle-p3j-v2-20261104` / client `up-b-m7-plk-cycle-p3j-v2` 仅规划，尚未在板卡创建。
原周期窗口与Linux归还窗口均已关闭，不删除或重用旧ATTEMPTED。后续如需硬件实测须新的独立授权。

## 本版解决的缺口

[原一次实际周期](../powerlink-cycle-p3j-hw-20261104/README.md)完成376TX后，旧runner将直接PRT任务也按pthread args0@48识别，清理失败并保留资源。
[独立授权归还](../powerlink-cycle-p3j-return-20261104/README.md)后来成功，但这两步不能冒充旧runner一次自动全流程成功。
本版把已验证的TCB检查接入**新的独立单次runner**，只修板端工具，不修改固件、历史runner/reader/结果或两个旧窗口。

新增 `read_powerlink_cycle_p3j_v2_snapshot.py` / `run_powerlink_cycle_p3j_v2_probe.py` / 新MICA配置。
复用固定P3j的候选身份、1504+608解码、COLD堆/完成查询和严格成功判据；新停核reader不调用旧错误的read_stopped。
直接PLKowner：taskEntry@32、静态ownerStack32768、ownerid/args/SP检查；RPMsg：实际OsPthreadWrapper@32、业务函数args0@48、两栈各4096。
要求候选cache/FSC ABI与TCB native/AArch64证明同时通过，且RTOS库SHA一致，才允许创建单次标记和移交资源。
TCB证明沿用上一阶段实际头/config编译得到的 `[800,16,20,24,32,48]`，不是本轮重新编译SDK或发现新布局。

固定流程仍为单次 `PLK cycle-probe` → 完整公开及live私有完成证明 → stop新client一次 → 独立CPU4/5 OFF前后读取1504+608/真实FSC/实际TCB → 全部合格后rm/rebind/卸hold。
成功报告增加全部TCB控制前缀、指针/上限，便于审计；不读堆内容、控制器MMIO或RTOS栈正文，不是栈水位/碎片/最坏实时证明。
未知/错误同样保留，不补发off、不第二次stop或重投。ACK模糊只观察，若后续证明完整可安全归还，但整轮仍标为失败而不抹去原通信错误。

## 范围不变

- 同一候选 `4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`，1220888B，不重建或替换正式ELF。
- 同一100ms或256次TX完成先到、总预算8s/4Mprocess、总提交≤1024，1MiB FSC及256KiB峰值余量；不是长稳或持续run API。
- 同一CPU5/ETH2/CNTP直驱，完整原OD和全部CN分配零；不新增CN业务/PDO/SDO或2oo3。
- 新CLI仅 `--confirm-isolated-p3j-v2-cycle`，新root/client/永久ATTEMPTED/AutoBoot=no；旧P3j或仅归还许可不能代用。
- [runtime-inputs.json](runtime-inputs.json)列22项精确未来输入及既有hold/日志器SHA；`prepared_only=true`，不是实际上传回执或执行许可。

## 实际软件验证

[Windows最终305项](windows-final-fixed.log)、[Linux最终305项](linux-final.log)通过，旧286+新19。
新增实际历史TCB的正确入口/ABI及错误数据拒绝、COLD/live helper不误用旧root、新配置与永久标记、22项平铺import闭包，和完整模拟流程。
工作流中**没有mock新read_stopped/TCB解码**，使用原实板采集的17项80B前缀、1504+608原始数据；OS/系统命令/PSCI查询/DRAM读取/RPMsg/网络边界全部模拟，绝无板卡IO。
成功路径验证一次命令、一次stop、OFF后读TCB、证明后rm、重绑后再卸hold；失败覆盖ABI/COLD/live proof/栈或wrapper/lease/堆/发布/bounds/异常/未完成/ACK/insmod/start/stop/恢复漂移。

[Windows17组完整回放](replay-windows.json)/[Linux17组回放](replay-linux.json)的结果和最终模拟状态完全一致。
绝对临时路径使原始系统调用trace不同，不声称两个JSON逐字节相同；回放明确 `software_only=true` / `hardware_executed=false`。
Linux另重新编译并运行原生产guard18+owner4回归，通过；明确复用11月2日 `software-repro` 核心库，不是本轮从头重建完整核心/累计ELF。

首个 [Windows失败](windows-first.log)是测试把“Linux driver已绑定”的true状态也要求清零；实际模拟结果已passed，修正测试为driver必须true，其余临时状态false。
最初 [303项](windows.log)/[首次305项](windows-final.log)保留。
[首次Linux命令](linux.log)因未上传旧runtime清单fixture，以及把临时stage布局当成标准repo相对路径而失败。
只补fixture并让单元测试同时核验精确bytes/SHA和标准包内相对路径，不放宽正式清单逐项核验；最终Windows/Linux完整通过，失败日志不覆盖。

## 换机复核与下一步

本轮构建服务器 `/home/openeuler/build/powerlink-cycle-p3j-v2-20261104`，未访问板卡。
在仓库根运行下列命令只复核归档/源包与补丁，不会执行硬件：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cycle_p3j_v2_checkpoint.py \
  /tmp/new-p3j-v2-prepared --expected-commit <当前检出提交>
```

新SHA清单继承776项历史源码/固定候选/证据路径，加入v2工具、配置、22项清单和回放/日志；旧清单不重生成。
只更新滚动memory/stage索引，既有源码及结果保持旧SHA。GitHub/服务器后验日志不纳入自身哈希，实际同步以最终报告为准。
按karpathy-guidelines限制为工具的最小修复，使用真实失败形态作回归，不把回放当新上板通过，也不扩大运行预算。

下一门槛是另获隔离回环与**一次v2自动闭环**授权，验证新版实际运行后可自动完成全部停核证明和归还；不能直接复用旧窗口。
之后再按对端型号/固件/XDD或CDC、NodeID、PDO数据和周期需求准备隔离CN互操作；真实CN/PDO/SDO/持续MN/最坏实时性仍未验收。
最近已知实际板卡状态仍是上一阶段Linux已归还的快照；本轮没有重新采样，未来授权后必须重新预检。
