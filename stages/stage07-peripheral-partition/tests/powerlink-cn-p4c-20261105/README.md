# P4c：Linux 软件 CN 的先静默后释放基础（2026-11-05）

本轮只做软件实现、模拟 IO 测试和新目录编译。没有连接板卡/COM7、运行真实 CN 或发送网络/CAN/串口帧；UP2 候选、正式固件和旧硬件窗口不动。
用户无实体 CN，继续 Linux ETH3 软件对端路线，不等待采购。这是**退出基础库**，不是已完成的 CN 应用或完整互操作验收。

## 这次修复

[生命周期门槛](../../source/powerlink/linux-cn/lifecycle/m7_cn_lifecycle.c)配合[固定源码变换](../../build/apply_m7_powerlink_cn_lifecycle.py)，只用于新解包的 Linux CN 树；原 P4a/P4b 源码、归档、产物及 UniProton 补丁链不改。

- 默认未 arm 时，`oplk_initialize` 在 target、共享 IPC、线程创建之前拒绝。arm 本身仍不是人的运行许可，也不是完整接口/进程前检。
- 跟踪四路实际栈线程：kernel event、hrestimer、user event、timeru；RX/TX 在途证明沿用原 P4b EDRV。所有栈线程共享原子停止请求；定时线程用 10ms 相对等待检查退出，不再 cancel；不设置 FIFO/RR 优先级。
- 先请求全部停止、调用 EDRV 自己的有界退出，然后以同一个 CLOCK_MONOTONIC 截止时间 join 四路栈线程。EDRV 自身最多 1s 合作式回收，另四路共用 1s；不能抢占卡死回调/系统调用，不是硬 2s watchdog。
- **所有来源确认静默后**才允许 user SDO/NMT/PDO、事件队列、定时对象、kernel PDO/DLL、timesync、对象字典等析构。单独调用四个异步模块的 exit 同样受门槛保护。timesync-local 没有独立线程，调用上下文来自这些已回收的生产者。
- 完整初始化必须包含四路注册及已激活、无错误的 EDRV；部分初始化即使线程已静默，也不能声称资源可释放。保留首错和资源，禁止再次 create/初始化/停止尝试。
- 第一个失败的析构立即返回，后续析构及环境清理不继续；若前面已有成功释放，不回滚、不声称全部资源原样保留，后续也不能重试这些析构。
- 保留 kernel cleanup 的实际返回值；失败不再被后续 OBD 成功覆盖，控制状态也不假报 Ready/Running/已退出。generic API 不提前清除待清理标记；成功后的重复 destroy/exit 无第二次 OS 动作，失败时也不重复 join/close/释放。
- 固定 CN/PDO/SOC-sync 配置，编译拒绝 MN/CFM/VETH/LED/store-restore 或独立 synctimer 扩展；不能把这个停止证明直接套到其他 profile。

整包仍按原 SHA/提交/1355 文件校验。变换另对 9 个指定文件检查规范化 LF 的 SHA，精确锚点全部通过后才写入新树；漂移/重复应用拒绝，不裁剪上游源码。

## 实际测试与复编

[控制层 C 测试](../test_powerlink_cn_lifecycle.c)链接构建库中实际 generic/ctrlu/ctrlk/lifecycle，模块 init/析构和 IO 边界模拟；26 个独立进程场景覆盖默认拒绝、部分 init、漏注册、thread-create 失败、四种 join 超时、时钟失败、网卡停止/在途/关闭/首错、user/kernel 析构和 kernel 返回值失败、错误 owner、重复 create/slot/退出、过早 kernel cleanup、环境清理失败。另含四路真实 pthread 在途回调回收。

[实际 worker C 测试](../test_powerlink_cn_workers.c)运行库中四路生产 worker 的 init、循环、回调和 exit；共享 IPC、POSIX timer/信号、EDRV 全部模拟，信号等待由 fake 提供有效定时对象，**不打开命名 IPC、不创建真实 POSIX timer、不打开 raw socket**。
测试私有 unnamed semaphore 仅用于本进程同步，真实 pthread/join 执行；四个回调同时进入后请求停止，全部返回且 join 后才能触碰释放边界。正常共 13 个释放观察点；队列释放/sem close/timer delete 失败分别保留后续资源，不继续重复动作。
这比仅检查字符串更强，但没有同时初始化/运行完整真实 OD/PDO/NMT/SDO 网络栈，也没有证明真实系统的共享 IPC 或定时信号寿命问题已经解决。

每个 native 新目录：**26 控制层 +4 实际 worker 场景通过**，测试编译 `-O2 -Wall -Wextra -Werror -UNDEBUG`；两个目录合计 60 次通过。库使用固定 CMake Release 配置；上游已有警告原样保留，不宣称整个库零 warning/Werror。

| 构建目标 | 库大小 | SHA-256 | 双新目录复编 |
| --- | --- | --- | --- |
| Native | 469396 B | fa2837fc528b176039e7feed93eab0ad7f81b49795b7cd2f90f57192e536996d | 库及 report 逐字节一致 |
| AArch64 | 433964 B | 51a6597a2731335178c25738b01efb943753aef7a19c2cfddb8a2d5b6e253419 | 库及 report 逐字节一致；不执行 |

[Native 日志](native-final.log)、[AArch64 日志](aarch64-final.log)均 EXIT0；两个架构的库、逐成员 ELF 头、两次 report 完整归档。Windows [352 项](windows-final.log)和 Linux [352 项](linux-tests.log)回归为原 340 +12，Linux 另记录实际最终输入 SHA。

诊断历史不覆盖：

- [native-first](native-first.log)：补丁后的文件 CRLF/LF 不同导致输入检查拒绝；改为仅规范化换行的文件 SHA，整包 SHA 校验仍保留。
- [native-second](native-second.log)：首 22 控制场景通过的中间版，不代替最终 26+4。
- [native-third](native-third.log)：控制 26 项通过后，新 worker 测试因单行 if 缩进的 Werror 未编译；改正测试排版，不降低编译检查。
- [Windows 首轮](windows.log)：测试仍寻找改造前的固定测试程序字符串，与按类别生成名字不符；只修边界测试期望，原 352 项失败日志保留。

## 换机复现

有既定构建容器/工具链时，仅生成库、native 运行模拟 IO 测试，不运行 CN；目录必须全新：

```bash
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_lifecycle.py /tmp/new-cn-lifecycle
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_lifecycle.py /tmp/new-cn-lifecycle-arm \
  --aarch64 --cc /home/openeuler/build/tl3572-2oo3/toolchain-14.3/bin/aarch64-none-linux-gnu-gcc
```

不执行 C 测试/peer 的离线校验：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cn_p4c_checkpoint.py \
  /tmp/new-cn-lifecycle-source-check --expected-commit <当前检出提交>
```

新清单继承 P4b 全部输入及后验日志，旧源码/证据/候选 SHA 不动，仅 memory/stage 索引滚动更新。服务器新目录 `/home/openeuler/build/powerlink-cn-p4c-20261105`；GitHub 全新克隆及 Linux delivery 的后验结果另存。

## 尚未完成／接下来

1. **共享 IPC 归属**：原 Linux event/circbuf 仍使用固定全局 semaphore/shm 名，并可能 unlink；本轮只模拟这些边界，不允许真实栈 init。要改成明确私有/独占、无跨进程破坏的方案并验证失败退出。
2. **定时器对象寿命**：原 timeru signal 携带堆指针；delete/free 与待决信号/回调的并发、timer-create 失败后的链表状态仍需处理。停止门槛只保证析构之前已 join，不自动解决运行时所有权问题。启动时 RX/事件激活与完整栈就绪顺序也须完整模拟联调。
3. 再做完整模块 init→处理→静默→释放的模拟 IO 联调、root/接口 IP 路由/其它进程/运行库兼容性/启动退出预算/永久窗口标记 frontend。当前没有可运行的受限 CN 应用，不执行旧 demo，包括 help。
4. 独立实现 CN-capable 有界 UP2 MN/decoder、明确 node240↔1/周期/MN+CN CDC/PDO/过程映像/事件验收；旧 P3j 的 no-CN/RX 拒绝保护不得放宽。

最近实板仍为 11月4日 P3j-v2 自动归还 Linux 的历史快照，不是本轮新采样。软件 CN 不等于工业/硬实时 CN；本轮不申请新硬件窗口、不复用已消费授权。
依照 karpathy-guidelines，把本次限制为可验证的退出基础及独立新构建，不在其他未闭合风险上开放运行入口。
