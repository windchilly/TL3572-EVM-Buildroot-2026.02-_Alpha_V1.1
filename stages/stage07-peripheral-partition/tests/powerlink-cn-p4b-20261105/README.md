# P4b：默认未授权的软件 CN 传输层（2026-11-05）

本轮只做离线软件实现/模拟IO测试及新目录编译，不连接板卡/COM7、不运行真实网络对端、不发送协议/CAN/串口帧，不改变UP2候选或正式固件。
原生rawsocket驱动退出和全局混杂模式存在缺口，先修复传输层资源生命周期；完整CN应用/栈退出、接口IP/路由检查和有CN的MN仍未集成，不能直接上板。

## 为什么先修传输层

固定上游原始`edrv-rawsock_linux.c`使用`SIOCSIFFLAGS`设置全局IFF_PROMISC；FIONBIO参数为0，接收可阻塞；exit只sleep100ms，没有join就销毁mutex/关socket，取消判断也不能证明线程已停。
另一个独立缺口是原`ctrlu_shutdownStack()`先释放用户层资源、原`ctrlk.shutdownStack()`先释放PDO/DLL等才调用edrv_exit。**修好驱动不等于修好完整栈退出**，不能把P4a原生demo换链接后直接运行。
这些是新引入的软件CN测试对端路径的上游既存问题，不是已通过的UP2/P3j退化；本轮完全不改UniProton旧源码/候选/保护判据。

## 本轮实现边界

新增[独立EDRV](../../source/powerlink/linux-cn/transport/edrv-m7-cn.c)和[元数据接口](../../source/powerlink/linux-cn/transport/m7_cn_edrv.h)，只在新解包树覆盖Linux CN rawsocket源文件，原P4a归档和产物不动。

- 默认未arm，init在socket前拒绝；arm只读验证固定`eth2`、SR9900 driver和板载USB路径`/1-1.4.1/`，绑定单owner线程。一次grant/init/stop尝试，模糊失败不重试。
- arm不是用户授权，也没有检查IP、路由、其它进程、内核/共享资源等；**还不能作为完整运行前检**。后续frontend必须补这些门槛和永久窗口标记。
- AF_PACKET socket使用NONBLOCK/CLOEXEC及POWERLINK EtherType；只读SIOCGIFINDEX/SIOCGIFHWADDR，绑定接口，不写地址/路由/全局网卡flags，不更改线程RT优先级。
- 用socket持有的PACKET_MR_PROMISC membership替代全局SIOCSIFFLAGS。成员由socket生命周期持有，close经内核释放；不覆盖其它进程的成员。API与释放依据见[Linux packet手册](https://man7.org/linux/man-pages/man7/packet.7.html)、[Linux v6.12 packet_release/packet_flush_mclist源码](https://raw.githubusercontent.com/torvalds/linux/v6.12/net/packet/af_packet.c)。这不是板端混杂计数恢复的实测证据，后续仍须前后核验。
- 接收过滤本机OUTGOING、错误接口/协议/长度/自身MAC，支持即时RX回调；错误请求deferred release时停下并保留静态RX存储，不继续复用。
- TX失败/短写不触发完成回调；成功只说明Linux socket接受，**不是物理线上完成、CN/PDO到达或实时性证明**。不沿用上游“断链也假完成”。
- 固定8s传输lease、最多2048次TX实际提交、4096次RX交付；poll10ms检查，退出采用CLOCK_MONOTONIC、1s timed join，等待在途回调清零后才能close。join/clock/close不明则保留状态/FD，不cancel、不杀进程、不二次join/close。
- 预算在调用边界检查，不能抢占卡死的回调或内核调用；不宣称硬8s watchdog。固定上限是软件防护，不是新的网络发帧许可或UP2周期预算变更。
- 首错fault保留；即使退出证明FD已关，`fault!=0`也不等于测试成功。`active=0`单字段同样不是停止证明，要联合joined/closed/inflight/stop标记及完整栈证明。

## 实际软件验证

[生产源C测试](../test_powerlink_cn_transport.c)通过link-wrap模拟所有socket/sysfs/绑定/收发/关闭边界，**没有打开真实raw socket**；其中一项使用真实pthread创建及CLOCK_MONOTONIC回收，其余join/线程故障边界受控模拟。
34种场景在每个全新进程执行，`-O2 -Wall -Wextra -Werror`：默认未授权、错driver/USB/网口/owner、各步init失败、成功/短写/发送失败、错误MAC/协议/busy buffer、TX/RX/时间预算、无效接收元数据/超长/本机帧、deferred拒绝、join超时、在途回调超时、close模糊/首错后clock错误，以及真实线程退出。
断言已停并join之后才close，超时不close，模糊close不第二次close，失败发送无回调；不是仅看源代码字符串或用mock报告代替实际生产函数。

首轮[native-first](native-first.log)编译后在deferred场景失败：测试误要求poll两次，生产代码正确在第一次回调拒绝后立即停下。只修测试期望为一次并核对RX存储保留，失败日志不覆盖。
[修正验证](native-fixed.log)34项通过，首版源/头[快照](history/first-edrv.c)与其build-report SHA一致；之后加元数据family/clock显式拒绝并重新做最终双目录构建。首轮模拟进程曾产生SIGABRT提示，core不上传；后续mock测试禁core dump。

| 最终目标 | 库大小 | 库SHA前缀 | 双新目录复编 |
| --- | --- | --- | --- |
| Native/x86_64 | 459730B | ee187e36… | 逐字节一致；每目录34项模拟IO通过 |
| AArch64 | 425674B | d74ba59f… | 逐字节一致；不执行交叉产物 |

[Native最终](native-final.log)/[AArch64最终](aarch64-final.log)均EXIT0，库与逐成员ELF头、两个目录的build-report另存。新增构建入口不生成或运行CN应用，只运行fake-network C测试，不安装系统文件/依赖。
Windows[340项](windows.log)/Linux[340项](linux-tests.log)通过，原330+新10；Linux记录实际最终builder/源/头/测试SHA。
完整栈其余部分仍是原生固定版本，编译告警原样保留；构建通过不代表原来整栈生命周期缺口已修好。

## 换机复核

有固定构建容器/工具链时，下列命令只生成库，并在Native目标跑模拟IO测试，不运行peer；输出目录必须不存在：

```bash
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_transport.py /tmp/new-cn-transport
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_cn_transport.py /tmp/new-cn-transport-arm \
  --aarch64 --cc /home/openeuler/build/tl3572-2oo3/toolchain-14.3/bin/aarch64-none-linux-gnu-gcc
```

离线复核产物/记录/340项回归及固定1355源文件与既有Linux构建补丁，不执行C测试或peer：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cn_p4b_checkpoint.py \
  /tmp/new-cn-transport-source-check --expected-commit <当前检出提交>
```

新清单继承P4a的870项及后验日志，旧清单不重生成，旧源码/固件/证据保持SHA，仅滚动memory/stage索引更新。构建服务器`/home/openeuler/build/powerlink-cn-p4b-20261105`；GitHub全新拉取与服务器delivery后验日志另存，以最终报告为准。

## 继续路线与未完成项

下一步先完成Linux CN的**完整栈先静默再释放**，联动RX、hrestimer/timesync、用户事件/定时器和OD/PDO资源，保留首错并为部分init/失败stop建立拒绝释放证明；再做根权限/接口IP路由/其它进程/启动退出预算/永久标记的frontend。不能仅给旧demo加timeout或SIGTERM包装就说安全。
随后实现独立有CN的有界MN候选及decoder，明确MN+CN CDC、node240↔1、PDO/CFM事件和过程映像；仍不放宽旧P3j的no-CN/RX拒绝判据。
软件对端不等于工业CN或硬实时；完整应用与整栈停止、MN/CN互操作、PDO/SDO及上板均未验收。本轮未请求新硬件窗口，也未复用旧授权。
按karpathy-guidelines把发现的底层生命周期缺口作为当前小步修复；没有在保护基础尚未接齐时开放可运行CN入口。
