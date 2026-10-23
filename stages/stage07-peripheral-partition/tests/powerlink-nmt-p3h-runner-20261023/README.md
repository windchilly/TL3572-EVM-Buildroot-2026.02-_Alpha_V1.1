# P3h 独立复测入口、真实堆检查与 ABI 准备（2026-10-23）

软件准备通过；**本轮没有连接、上传或部署板卡，也没有接管 ETH2/CNTP、reset、发帧或重启**。
这不是 P3h 实板结果，更不是持续 MN/CN、PDO/SDO 或1ms周期验收。
上一[P3h软件修复](../powerlink-nmt-p3h-20261023/README.md)与[P3g失败/一次授权恢复](../powerlink-nmt-p3g-hw-20261023/README.md)保持原记录。
板卡最新已知状态仍来自上次恢复，不能把本轮无板卡操作描述成新状态快照。

## 新窗口与许可边界

- 仅接受原固定 P3h ELF `ccfba235f8f3bcc79ab0c2a0e603b2d9cc01a7f3785985566660fb1672882ea8`，没有重编或改变运行固件。
- 计划新根 `/root/m7-powerlink-nmt-p3h-20261023`、client `up-b-m7-plk-nmt-p3h`、AutoBoot=no；本轮尚未在板卡创建。
- 独立 `run_powerlink_nmt_p3h_probe.py` 和 `--confirm-isolated-p3h-nmt-reset`，新永久 ATTEMPTED 单次标记/独占结果文件。
- 保留旧 P3g runner、固定SHA、目录和已用ATTEMPTED，不覆盖、不重投，不更改正式配置或开机配置。
- 复用旧入口的四条诊断白名单/只观察完成逻辑，不修改其模块全局量；新客户端停止、私有证明和堆检查走独立入口。
- 只运行一次现有有界 `SwReset→MN NotActive→立即SwitchOff→GsOff→静默停止/退出`，不执行持续MN/StartNode或外部任意NMT。
- 接线、隔离及新单次窗口必须重新确认。旧P3g物理许可和上次“重启恢复+软件修复”不授权本次上板。

## 堆检查是新增的真实资源门槛

`powerlink_nmt_p3h_checks.py`为无IO纯校验，`read_powerlink_nmt_p3h_snapshot.py`只读私有DRAM小范围元数据。
不遍历堆、不访问GMAC/PHY/GIC控制器MMIO，不发送或执行停止/恢复命令。
live COLD只是点时双读预检，不是原子快照或跨核缓存一致性的独立实测；未初始化/不一致时不提交NMT，保留资源，不循环重试到通过。

| 阶段 | 必须取得的证据 | 不代表什么 |
|---|---|---|
| 启动后、唯一命令前 | 新COLD owner/seq0、全部旧probe缓存0、ETHlease0、异常cause/ELR/ESR0；真实FSC计数两次一致 | 不是停核或DMA静默证明 |
| NMT完成后 | 缓存与RPMsg证明reset/off各1次、NotActive实际到达、最终COLD、lease/工控idle/停止回读均合格 | 不直接允许rm/重绑 |
| 一次stop并独立确认CPU4/5 OFF后 | 1504B缓存、异常0、lease0、真实TTY/listen栈各4096B；真实FSC总量/usage/peak、RPMsg/私有证据一致 | 不是控制器MMIO独立再读或最坏实时/碎片证明 |

FSC池必须为1MiB，`g_memStartAddr`等于ELF池地址，`g_memTotalSize=1048544`（池减32B末端控制头）。
必须满足 `0≤used≤peak≤total`；不接受旧512KiB总量、不稳定读数、越界地址或异常缓存。

启动前可用堆须至少767888B，即上一P3h宿主模型的PLK峰值505744B加256KiB余量；
停核后实际峰值也必须至少留下256KiB。505744来自636816-131072的显式宿主压力模型，
**这是本轮保守验收门槛，不是实际RTOS最坏分配上界或协议规定值**。
不足/异常时终止并保留资源；不会为了通过而缩减PDO通道、修改固件或自动扩大堆。
记录前后used差值，不把单轮差值当作严格泄漏结论；RTOS/RPMsg背景分配也包含在计数中。

## 停止与故障保护

只有成功完成证明与初始堆证据合格后才允许一次stop；物理CPU OFF后，私有快照/真实堆/线程栈和RPMsg一致，
才可rm临时client→重绑Linux→恢复100Full/ANon/link→复核管理口/工控/micad/boot→去hold。
短写或ACK超时只观察，不第二次提交；任何未知阶段不自动强停、重绑、去hold或重启。
即使已经停核，只要私有/堆证明失败，也不第二次stop或自动归还。
仅接管前失败且确认CPU OFF的路径可以按原规则回滚已知Linux状态，不做泛用恢复。

## 编译与回归证据

[首次Linux完整回归](linux-first.log)、[最终Linux回归](linux-final.log)、[Windows203项](windows-current.log)：

- 原175项 + 新28项：固定新旧身份、实际ELF/地址、ABI JSON、FSC计数/余量、COLD/异常/不稳定读、停核前后读顺序及真实线程栈。
- 全流程完全模拟系统/终端：成功停止归还、命令前堆失败保留、NMT失败保留、模糊ACK只观察、私有证明失败后不重停/重绑。
- 原生27+4 NMT与全部旧P3f/P3e/P3d/P3c/P3b/累计回归通过。
  本轮原生harness重新编译链接，核心库/旧CTest二进制明确复用已验证P3h `software-repro`，没有声称本轮从头重编核心。
- 首次Windows mock未提供该平台缺失的POSIX open标志，测试在模拟启动后报错；[原始失败](windows-first.log)保留。
  只给fixture补标志值并继续mock os.open/close/终端，不改变Linux板端代码；最终203项通过。中间202项日志也保留。

`audit_powerlink_nmt_p3h_abi.py`两次使用native GCC和固定14.3 AArch64 GCC：
[第一次](p3h-abi.json)/[第二次](p3h-abi-final.json)逐字节相同。
实际头文件23项缓存布局一致（1504B/offset80/result496/life472），
从固定RTOS头文件提取完整 `TagFscMemCtrl` 声明、原样独立编译，确认控制头32B/uintptr8B；
核对真实FSC初始化源码的减头/total/start关系，记录源文件/头文件/libRK3572 SHA。
这不是运行RTOS分配器，也没有重新发现M6 TCB stride800/异常520的私有偏移；这些仍为固定M6 ABI。
板端必须具备匹配 `p3h-abi.json`，其候选SHA/双编译器布局/私有符号地址与ELF均须一致。

## 换机复现与归档

构建准备根 `/home/openeuler/build/powerlink-nmt-p3h-runner-20261023`，Docker `dev_openeuler`；
`stage/`只作软件/归档检查，原P3h核心和累计构建目录不改，delivery保存本次精确清单。
先恢复[固定M6源码/SDK/摘要Docker](../../../../repro-inputs/rk3572/README.md)和[固定P3h候选构建](../powerlink-nmt-p3h-20261023/README.md)，进入stage07：

```bash
python3 tests/audit_powerlink_nmt_p3h_abi.py \
  tests/powerlink-nmt-p3h-20261023/candidates/tl3572-m7-powerlink-p3h-up-b.elf \
  /path/to/UniProton /path/to/toolchain-14.3 /tmp/p3h-abi.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

[runtime-inputs.json](runtime-inputs.json)列未来新窗口必须平铺的21个精确输入（含ELF/ABI/conf/全部依赖），
以及既有hold模块的独立路径/哈希。这只是准备清单，不是上传回执或执行授权。
`make_powerlink_p3h_runtime_inputs.py`只生成本地清单，不连接板卡。
`SHA256SUMS`列当前完整源码/依赖/证据；旧清单到各自历史commit核对，不重生成。
后验GitHub日志不纳入自身清单；`verify_powerlink_p3h_runner_checkpoint.py`验证精确SHA、21输入、双ABI证明、
203项和真实1355文件/0001–0007补丁，并确认原P3g runner不变，没有板卡路径。
GitHub同步及服务器交付状态以最终报告为准。下一步另问隔离回环与P3h单次受控NMT窗口，不直接持续运行MN。
