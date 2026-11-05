# P4d：软件 CN 私有资源与代际定时器（2026-11-05）

只构建库及运行有网络入口保护的进程内资源/模拟 IO 测试；没有连接板卡/COM7、运行真实 CN、发网络/CAN/串口帧、修改 UP2 或正式配置，不复用旧硬件窗口。
用户无实体 CN，继续 Linux ETH3 软件从站对端路线，不等待采购。**这不是 UP2 主站/CN 网络互操作验收，也没有提供可运行 CN 应用**，runtime_ready=false。

## 本轮改变

[新源码](../../source/powerlink/linux-cn/private/)和[新变换入口](../../build/apply_m7_powerlink_cn_private.py)只用于固定 Linux 单进程 CN/PDO/SOC-sync 配置，先校验原始输入，再叠加完全不变的 P4c 基线。
旧 P4a/P4b/P4c 源码、补丁、产物和 UP2/UniProton/P3j 候选及 no-CN 保护不改。

- event CAL 改为两个 unnamed semaphore（pshared=0）。kernel 创建/最终销毁，user 只 attach/detach；全部线程静默且 user detach 后才允许最终销毁，失败不二次销毁。部分初始化保留现场。
- circbuf 改为进程私有堆缓冲和静态私有 mutex；同 id 的两层共享实例，owner/connector 引用计数，owner 先关闭时不接受新连接，但保留存储直到已有 connector 断开。重复 owner/多余 connector 拒绝；每队列上限 1MiB、固定 20 个 id。
- 无 sem_open/sem_close/sem_unlink、shm_open/shm_unlink/mmap 资源路径，不会按固定系统名称覆盖或删除其它进程的队列。数据、计数和 signal callback 注册/读取受锁保护，通知在解锁之后调用；修正 event queue 索引对负数/数组末端的越界检查。
- 两类定时器改为固定存储 + CLOCK_MONOTONIC condition variable，保留原 hres/user 两个受 P4c 跟踪的 worker；hres 2 槽、user 64 槽。deadline 改动会唤醒，最长 10ms 检查停止；单次 20us/连续 100us 最小 hres 间隔沿用上游约束，但**不保证 Linux 调度精度或工业硬实时**。
- 不创建 POSIX timer、不使用 timer signal、不把定时器堆对象指针放进事件。句柄是有域/槽位/代际的 64 位数字；删除/修改再重建不会使旧句柄指向新对象，代际耗尽拒绝而不回绕。
- 超时先在锁内复制参数，解锁后调用；删除不会使已提交的回调快照悬空，但不能撤回已提交回调。应用传入的 pValue 仍属于应用，必须保留到其回调完成/整栈静默，不能据此宣称任意应用指针都已自动安全。
- user timer 事件在 user/kernel 实际 dispatch 前验证并消费代际，已删除/修改的旧事件和重复事件丢弃；不解引用其应用参数指针。0ms user timer 明确为一次立即到期，不沿用原 POSIX zero-value 的意外 disarm 行为。
- timer fault 在完整 init 与释放门槛处检查。停止后不再启动新 timer；资源销毁失败保留首错及后续资源，不反复尝试。静态私有 mutex 不销毁，生命周期不得 fork 后继续使用。
- target_init/cleanup 不再设置 timer signal mask 或切换全局 ftrace。event worker 同样改用 CLOCK_MONOTONIC/sem_clockwait，避免壁钟调整改变等待基准。

完整联调确认还存在第三个 unnamed semaphore：上游 PDO 的 `/pdoMutex` 名字仅作参数，Linux target-mutex 实际忽略名字、pshared=0，并非命名 IPC。
补修其销毁失败路径：不再忽略 sem_destroy 错误后 free；PDO exit 保留互斥引用与通道，立即传播首错，不继续释放。也检查 PDO exit 的 lock 返回值。

## 实际软件验证

每个全新 native 构建执行 **55 个顶层 C 场景**：

1. 原 P4c 的 26 个真实 generic/ctrlu/ctrlk 生命周期控制场景，仍使用受控模块/IO 边界。
2. [25 个私有资源/定时器场景](../test_powerlink_cn_private.c)：真实队列往返、owner 提前关闭、5000 条双线程有序收发、独立 exec 子进程不能连接父进程队列、分配/索引边界；semaphore init/destroy 失败；真实 hres/user worker、到期/周期/修改/删除重用/在途快照、旧/重复事件拒绝、容量/无效句柄/时钟/线程/cond/post 失败。
3. [4 个实际栈联调场景](../test_powerlink_cn_private_stack.c)：原 CiA401_CN 对象字典 +真实 user/kernel/OD/PDO/NMT/SDO/event/timer 模块，只有 EDRV/网络入口模拟。正常 create→两条内部 user event→128 次 process→destroy/exit，用户 NMT 保持 GsOff；另验证 EDRV 部分 init 失败、第四线程创建失败、PDO mutex destroy 失败。

完整栈正常：4 线程创建/4 join/1 EDRV stop，2 个 API user callback，3 个 sem_destroy（2 event +1 PDO）、2 个 cond_destroy，私有队列归零。
部分 EDRV/线程初始化失败：分别回收 2/3 个已创建线程，3/6 个队列保留；PDO destroy 失败：4 join 后只尝试一次 mutex 销毁，6 个队列和后续 timer 资源保留。重复 destroy/exit 不再 stop/join/销毁。
这些是模拟 EDRV 的被动软件结果，不是 PHY/RX/TX、POWERLINK NMT reset/start、PDO/SDO 网络业务或板端证明。

测试入口对 socket、命名 IPC、POSIX timer、system/RT 调度/NMT 命令等设拒绝保护；没有运行 demo，原生真实线程/unnamed sem/condvar 仅影响本测试进程。
测试编译 `-O2 -Wall -Wextra -Werror`；原 CiA401 OD 单独按上游标志编译，上游库/OD 警告原样保留，不称整个库零警告或全栈 sanitizer/无泄漏证明。
独立进程隔离场景还启动一个 helper 子进程，其 PASS 不重复计入 55 顶层场景。两次 native 构建合计 **110 次顶层场景通过**。

| 构建目标 | 库大小 | SHA-256 | 复编 |
| --- | --- | --- | --- |
| Native | 484890 B | 4b1d52236d2abbba36e0e993cd9035673f1d6bf6856751284d91f8a84a9e264f | 双新目录库/report 完全一致 |
| AArch64 | 448226 B | bffdc57545fea3104e7dae3d74089266c6921f3936539bb778d06a66a0c77815 | 双新目录一致；不执行 |

[Native](native-final.log)/[AArch64](aarch64-final.log)均 EXIT0；库、逐成员 ELF 头、undefined symbols、两次 build-report 已归档。
两个库的 undefined symbols 均没有命名 IPC 或旧 POSIX signal timer 的 10 类入口；原 signal timer 源文件仍在完整解包树中，但明确从本 profile 的编译输入移除。
Windows [368 项](windows-final.log)/Linux [368 项](linux-tests.log)回归 =原 352+新16；Linux 另核实际最终输入 SHA。

诊断历史保留：native-first 为新头文件 include 路径错误；native-second 首 26+25 通过；native-third 的联调测试用了上游并不存在的 nmtk_getNmtState，Werror 拒绝后改用实际 nmtu_getNmtState；native-fourth/fifth 为测试少算 PDO 私有 semaphore，fifth 实际计数 3 已留；native-sixth 完成前三个被动联调，中间结果不代替最终增加的 PDO 销毁失败保护。
没有降低编译保护或改写失败日志；模拟测试 abort 的日志提示保留，core 禁用且不上传。

## 换机复现与交付

固定容器/工具链准备好后，输出目录必须不存在；仅生成库，native 仅运行上述有 IO 保护的测试：

```bash
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_private.py /tmp/new-cn-private
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_private.py /tmp/new-cn-private-arm \
  --aarch64 --cc /home/openeuler/build/tl3572-2oo3/toolchain-14.3/bin/aarch64-none-linux-gnu-gcc
```

不执行 C/CN 的离线校验：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cn_p4d_checkpoint.py \
  /tmp/new-cn-private-source-check --expected-commit <当前检出提交>
```

新清单继承 P4c 全部输入/后验日志，旧证据不重生成；仅滚动 memory/stage README。服务器新目录 `/home/openeuler/build/powerlink-cn-p4d-20261105`。
GitHub 全新克隆及服务器 delivery 各独立校验哈希/368 项/完整 1355 文件和新变换，后验日志单列，不等于又执行了一轮 C/CN 或实板测试。

## 下一步与边界

被动完整栈闭环已过，仍需：启动时 RX/事件激活与全栈 ready 的约束、主动处理/错误注入的模拟联调，以及受限 frontend 的 root/接口 IP 路由/进程身份/运行库兼容性/预算/永久窗口标记。
之后再准备独立有 CN 的 UP2 有界 MN/decoder、明确 node240↔1/周期/MN+CN CDC/PDO/过程映像/验收；不能直接放开旧 P3j no-CN/RX 拒绝保护。
没有实体设备不阻塞软件路线，但软件 CN 不等于工业/硬实时 CN。最近实板仍是 11月4日自动归还 Linux 的历史快照，不是本轮新采样；运行真实 CN 或移交 ETH 必须另开新窗口。
按 karpathy-guidelines 将改动限制在 Linux CN 私有资源和定时器，相关 PDO 析构失败传播一并补齐，不修改 UP2 路线或替换正式固件。
