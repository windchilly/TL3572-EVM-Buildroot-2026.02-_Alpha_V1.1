# P4e Linux 软件 CN 全栈就绪门槛（2026-11-05）

结论：P4e 软件验证通过。新增整栈完成后的单次接收激活，以及 RX/TX、事件、定时回调的共同就绪门。仅 Linux 软件 CN 库；`runtime_ready=false`，仍不可运行真实 CN/demo（包括 help）。

本轮没有连接 `192.168.2.141` 或 COM7、移交 ETH2、运行真实 CN、发送网络/CAN/串口帧、重启或改正式配置。服务器仅连接构建主机 `10.100.60.226` 的 `dev_openeuler`。最近实板状态仍是 11 月 4 日 P3j-v2 的历史归还记录，非本轮重采样。

## 修改与边界

新 `build/apply_m7_powerlink_cn_startup.py` 叠加不可变 P4d 变换，先复核其完整 23 文件生成 SHA，再生成本轮 25 文件 SHA。不改 P4a–P4d 的源码、构建器、测试、证据或产物，也不改变 UP2/P3j 的 no-CN、拒绝 RX 条件。

1. `edrv_init` 只创建 `AF_PACKET/SOCK_RAW|NONBLOCK|CLOEXEC`、协议号 0 的套接字，读取固定 eth2/SR9900 身份/MAC、设置 socket 级 membership，启动等待中的 RX 线程，不绑定接收协议。Linux [packet(7)](https://man7.org/linux/man-pages/man7/packet.7.html) 明确协议 0 不接收报文，因此不存在初始化期间接收队列积压再交付的问题。此语义为文档依据，模拟边界并非真实内核套接字实测。
2. user/kernel/OD/PDO 全部 init 成功、四个栈线程登记齐全、传输及 timer 健康后，由 owner 一次 `bind(eth2,0x88ab)`；绑定成功才以原子 release 发布 ready。绑定时完整栈已完成，但派发门仍关闭；此时到达的帧是完整初始化后的帧，不是部分初始化时的积压。
3. RX worker 在 ready 前不 poll/recv，TX 在参数处理与进入传输前拒绝；eventk/eventu 线程不取队列，hres/user timer 不派发。内部启动事件可复制进有界私有队列，定时槽可以准备，到 ready 后才处理；过期连续 timer 仍跳过漏周期，不突发补发。等待门的线程每 1ms 协作检查 stop，无取消或强杀。
4. 停止或任一记录的 worker/传输/定时错误关闭 gate 并设置 stop。首错统一原子记录和读取；owner 快照不再非原子复制整个含首错的结构。事件时钟、sem wait/post 和 dispatch 返回错误均进入同一停止路径。
5. 关闭 gate 只拒绝新准入，不能抢占已准入回调；仍须原 EDRV 在途归零、EDRV join + 四线程 join 全部证明，再允许逐项释放。未知 join/close、部分 init 或任何首错不释放栈资源、不重试；此前析构已有部分释放时不回滚。协议 lease 仍自 EDRV init 起算 8s，不因 ready 延长；2048 TX/4096 RX、原 join 预算不变，非硬 watchdog。
6. `oplk_execNmtCommand`、`oplk_process`、`oplk_postUserEvent` 及直接 event dispatch 加 ready 检查；这不是对全部上游 API 的并发线程安全或完整 frontend 授权证明。arm 与 ready 都不是用户许可，仍未核验 root/IP/路由/其他进程/运行库/永久窗口。

## 验证结果

| 项目 | 结果 |
| --- | --- |
| Native GCC 12.3.1 | 静态库 490,956 B，SHA256 `f0c7e1e9c810518bce3ff55878de04c28b857e7a6748b315f243364e186b2f68` |
| AArch64 GCC 14.3.1 | 静态库 454,204 B，SHA256 `a29e046a5c107511eb8c6341d0310edf47fbfd96d5cdb09df366305ac9072e5b` |
| 双新目录构建 | 两种架构各自库与完整 build-report 逐字节相同；AArch64 产物未执行 |
| C 顶层测试 | 每次 25 control +25 private +17 实际栈/EDRV 模拟 IO =67，两个新目录共 134 PASS |
| 私有队列隔离 helper | 每次另 exec 一个 helper，未重复计入 67 |
| Python | Windows/Linux 各 380 =原 368 +新 12，通过；Linux 另记录实际编译输入 SHA |
| 禁用引用 | 两架构库均无原 10 类命名 IPC/POSIX signal timer 未定义引用 |

25 项 control 复用原 P4c 模拟模块测试；原 `early_kernel_cleanup` 旧 fixture 要求出错后生产者继续运行，与本轮主动关闭 gate 的语义不符，故不运行该旧断言，改由新的完整栈同名场景验证 fail-closed。25 项 private 复用旧测试，在组件隔离层显式模拟 ready；真实 gate 由下列完整栈场景独立测试，不靠该模拟证明。

17 项完整栈场景链接真实 generic/ctrlu/ctrlk/OD/PDO/NMT/SDO/event/private timer 和真实生产 EDRV，并编译上游 CiA401_CN OD。只有 socket/sysfs/ioctl/bind/poll/recv/send/close 等网络 OS 边界模拟，实际运行四个栈 worker 加一个 EDRV worker；未使用旧 P4d 的 EDRV 整体替身。

- 五个真实线程都存在而 init 尚未返回时，排队一个内部事件、准备 user 零延时和 hres timer，等待约 20ms，证明 poll/recv/send/用户回调/两类 timer 派发全为 0。另有四线程阶段 20ms 检查；时间只是测试等待，不是实时保证。
- 正常、一次模拟 RX、一次模拟 TX 提交：5 create/5 join/1 bind/1 close；1 用户回调/1 hres/1 user timer；3 semaphore +2 cond 销毁，队列引用为 0。RX 使用 GsOff 下未知类型 0xff，不执行 reset/start 或产生响应；TX 是驱动层虚拟边界接受，不是线侧完成或真实 POWERLINK 互操作。
- 绑定失败、第五线程创建失败、socket 失败、启动超时、启动期首错：无用户/timer 回调、无模拟收发；除绑定失败的一次尝试外 bind=0；部分资源保留。socket 失败时已创建 eventk/hres 两线程，而非只有一个。
- TX 短写、RX IO、sem wait/post、event worker clock、user timer 投递、应用 dispatch 失败：关闭 gate、保存首错，join 后仍不释放栈；应用 dispatch/user timer/启动首错均保留 `kErrorNoResource`。
- join 模糊场景：测试替身先实际 join 线程保证测试进程安全，再回报 ETIMEDOUT 模拟“调用方无法证明停止”；close=0、析构=0，保留资源，不是实际挂死线程/真实超时实测。
- 各失败及成功状态再次 exit/destroy 不增加 join/close，失败首错不变。

原上游警告保留；新增库使用 `-Werror=implicit-function-declaration`，测试用 O2/Wall/Wextra/Werror，原 OD 单独编译保留其原有警告。未声称全栈 sanitizer、严格无泄漏、并发压力、硬实时或互操作通过。

## 原始失败与中间结果

`native-first.log`：新 EDRV 缺少生命周期声明包含而产生 implicit-declaration 警告；同轮正常/绑定失败/部分线程保护已过，socket 失败 fixture 把已创建线程误数为 1（实际 2）而失败。补齐头文件并将隐式声明升级为编译错误，修正计数，原日志不改。

`native-second.log`：socket 失败后测试发送被源 MAC 参数校验拒绝，尚未返回统一“门关闭”错误。将 TX ready 检查前移至参数处理前，真实零发送边界不变；保留原失败，不放宽断言。

`native-third.log`：上述修正后 66 场景通过。最终再增加五线程同时等待门的检查和 dispatch 错误场景，形成最终 67 场景，使用两个新目录重新构建/测试。最终原始日志 `native-final.log` 和 `aarch64-final.log` 各含双目录构建及 cmp。

测试进程禁用 core（RLIMIT_CORE=0），失败日志中的 SIGABRT/core 提示保留；没有下载或提交 core 文件。

## 换机复现

使用此前固定 Docker 摘要/工具链联网取得构建环境，完整固定上游归档仍为 2.7.2 /commit `048650a80db37fa372330c3a900d2c8edb327e47` /1355 文件。先按本目录 `SHA256SUMS` 校验全部输入，然后在 **Linux 构建环境** 中以仓库根为工作目录：

```sh
python3 -B stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_startup.py /path/to/new-native-output
python3 -B stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_startup.py /path/to/new-arm-output --aarch64 --cc /path/to/aarch64-none-linux-gnu-gcc
```

每个输出目录必须不存在，构建器不会覆盖。Native 只运行模拟 IO 测试，不运行 CN；cross 只编库。另建第二组目录可对照库和 report。生产源码变换只写新解包树，不修改仓库历史源码。服务器独立目录 `/home/openeuler/build/powerlink-cn-p4e-20261105`；原阶段目录均保留。

`verify_powerlink_cn_p4e_checkpoint.py` 只审计证据/SHA、运行 Python 离线回归、在新目录恢复源码，不执行 C/CN/板卡 IO。`github-verification.log` 与 `server-verification.log` 是后验独立日志，不包含在本阶段自身清单内，随后单独提交；来源提交与清单数量见日志。旧 P4d 清单和两后验日志均在新清单内。

下一步仍在软件侧：受限 frontend 的身份/权限/IP路由/独占/运行库/预算与永久窗口检查，后续独立 CN-capable 的有界 UP2 MN、decoder、匹配 CDC/PDO/过程映像，再申请全新隔离互测窗口。当前无设备不阻塞软件准备，不放宽 P3j 的 no-CN 保护，不把本轮组件就绪当作真实软件 CN 上线许可。
