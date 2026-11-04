# P3j 停核后仅资源归还（2026-11-04）

结论：**单独授权的停核后资源归还 PASS，Linux 已恢复。没有重新执行周期。**

用户另行确认：“允许核验后仅清理并归还 Linux”。
只核验同boot、CPU4/5 OFF、原缓存/真实堆/修正TCB/管理工控基线，随后移除已停临时client、重新绑定Linux ETH2并卸载hold。
不再加载、启动或停止UP，不重跑周期，不开COM7/发送UP2测试或CAN/串口帧，不重启；不一致保留，不重试。
原[周期及清理失败记录](../powerlink-cycle-p3j-hw-20261104/README.md)与ATTEMPTED不覆盖，归还另存独立结果和永久单次标记。

## 实际核验与归还

执行前源码提交 `659bfb795fea63204978838f65ccde9269bff66e`。
[只读预检](preflight.log)确认仍为原boot `63986874-c4a0-4c1a-95b0-a92deb7f3bae`、micad PID329/NRestarts0/active、CPU4/5 OFF、三client均Offline及ETH2/hold保留状态。
[基线输入](baseline.json)来自原始BEFORE、完成结果、真实停止缓存/堆/TCB与19输入回执；另固定6项正式固件/配置/hold/日志器SHA。
新建临时工具子目录 `/root/m7-powerlink-cycle-p3j-20261104/return-linux-20261104`，只上传新归还脚本、已修正的纯TCB检查器和基线3项。
[3项实际上传读回回执](board-input-sha256.json)完全匹配；旧19项和原失败结果在归还前后重新核对不变。

再次独立确认CPU4/5 OFF，稳定读取原1504+608缓存、lease/异常0、真实FSC、全部17项TCB控制前缀，再确认OFF。
两份缓存和17项TCB逐字节等于第一次保留现场；真实FSC仍total1048544/used38584/peak543648/峰余504896，used差1064仅记录。
实际直接PLKowner入口@32/ownerid6/静态32768栈，以及pthread包装器@32/业务函数args0@48/TTY和listen各4096均合格。
原micad/管理口地址路由/工控寄存器与驱动绑定基线、内核无Oops/无RPMsg端点等均在动作前后核验。

独占创建 [LINUX_RETURN_ATTEMPTED](LINUX_RETURN_ATTEMPTED.txt)，仅执行以下4项一次性动作：

1. 移除已停止的 `up-b-m7-plk-cycle-p3j` **实例注册**；配置/ELF/日志/原ATTEMPTED均保留。
2. 将 `2a040000.ethernet` 重新绑定Linux `rk_gmac-dwmac`。
3. Linux `eth1`（板上ETH2）置UP，等待两端恢复100Full/ANon/linkyes。
4. 完整基线与链路合格后卸载 `m7_eth2_power_hold`，再做最终核验。

[原始归还日志](board-return.log)、[独立归还结果](return-result.json)：`passed=true`、`cycle_reexecuted=false`、`cpu_stop_issued=false`，4项attempted/completed完全相同且无错误。
没有调用UP start/stop/create/CPU_OFF/TTY写入/周期命令，没有重新加载或重启；不会把旧runner的EXIT1改成0。
`rm`仅移除临时实例注册，未删固件或证据文件；以后若获新的测试授权可由保留配置建立新窗口，不得复用旧一次性标记。

## 只读后检与当前状态

[只读后检](postflight.log)确认：

- 原 `up-a/up-b` 两实例Offline，CPU4/5物理OFF；临时实例和RPMsg端点已清除。
- 板上ETH2/ETH3分别Linux eth1/eth2，均100Mb/s Full、ANon、linkyes，hold模块已卸载。
- 管理板上ETH1/Linux eth0地址192.168.2.141/24及路由、micad PID329/NRestarts0/active、boot均保持。
- CAN0..3全部DOWN，failed服务0，taint4096且无Oops128；正式M6两ELF SHA9c5e55a2.../3357eb97...及配置保持，正式M7/DT/kernel/开机未改。

本次只是归还，不产生新的UP2周期/测试/CAN/串口数据；Linux驱动重绑后的常规协商/后台网络不等于UP2测试发帧。
原一次P3j隔离运行曾完成376TX/IRQ和回调376、自然Operational并退出；结合本次独立归还，开发切片现已安全闭合。
这仍不是原自动runner一次全流程PASS，也不是持续MN、真实CN/PDO/SDO/伺服或1ms最坏实时性验收。

## 软件与离线复现

Windows/Linux各286项（旧273+归还13项）通过，覆盖CPU未停/缓存、堆、TCB变化、门槛/永久标记拒绝、rm/bind/linkup/unload结果不明、链路超时、基线漂移和精确动作顺序。
真实RTOS TCB几何沿用上一阶段两次native/AArch64编译证明；本次没有重编固件或核心。
按karpathy-guidelines将新授权限制为独立一次性归还，不修改历史runner/失败记录；修正检查必须先证明，再执行资源动作，任何失败不重试。

在仓库根离线复核，不访问板卡：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cycle_p3j_return_checkpoint.py \
  /tmp/new-p3j-return-prepared --expected-commit <当前检出提交>
```

新清单继承758项历史路径和源码，加入本次3输入回执、日志、基线、结果、标记与归还源码；旧清单保持。
历史“仍保留现场”只描述原失败阶段；最新归还状态以本目录为准，原失败JSON仍为false。
GitHub/服务器后验日志不纳入自身清单。服务器交付为Docker dev_openeuler中的 `/home/openeuler/build/powerlink-cycle-p3j-return-20261104/delivery`，实际同步状态以最终报告为准。
本次授权已结束，不因“继续”自动重复归还或周期；后续优先软件计划，任何新的物理周期/CN窗口另行确认。
