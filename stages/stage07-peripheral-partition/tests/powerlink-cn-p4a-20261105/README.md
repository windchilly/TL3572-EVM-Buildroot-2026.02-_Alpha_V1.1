# P4a：无实体设备的 Linux 软件 CN 准备（2026-11-05）

用户确认目前没有 POWERLINK CN 设备。本轮仅准备软件对端和离线配置检查，未连接板卡/COM7，不接管或发网络/CAN/串口帧，不部署或执行 CN，不修改正式固件。
后续拟用 Linux ETH3 软件 CN ↔ UP2 ETH2 MN 做隔离协议互操作；软件对端不能替代真实工业CN/硬实时验收。

固定P3j不能直接接CN：其0x1F81各节点分配须为0，且任何RX交付在生产probe及板端decoder中均会被拒绝。旧固件及判据保留，未来须独立CN-capable候选和新有界runner，不套旧授权。

## 已完成的软件工作

1. [只读基线报告](baseline.json)核对原固定1355文件源码归档/提交、当前15B内置CDC、P3j候选SHA及生产/decoder的no-CN门槛；[Linux同一报告](baseline-linux.json)逐字节一致。不是新板卡状态快照。
2. [CDC检查工具](../../build/inspect_m7_powerlink_cdc.py)按LE计数/16位index/8位subindex/32位长度解析，保持写入顺序和重复项，不会擅自去重PDO关闭→映射→启用序列。显式MN scope才展开一层0x1F22的CN concise配置；默认unknown不猜目标。1MiB/4096条、非空/无尾字节是本项目严格审计子集，不是完整标准或OD语义验证，不生成配置或启用节点。
3. [独立Linux CN构建入口](../../build/build_m7_powerlink_linux_cn.py)使用固定openPOWERLINK V2.7.2、原CiA401_CN对象字典和demo_cn_console；只选择Linux CN库与raw-socket EDRV，不编MN、内核驱动或额外pcap服务，不安装系统包。
4. [Linux专用补丁](../../source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch)仅两处：CN little-endian构建接受aarch64；CN demo明确选择rawsocket时不无条件链接pcap。只应用新解包树，不加入UniProton既有0001–0007或修改旧源码。
5. [软件对端计划](../../config/powerlink-linux-cn-peer.plan.json)：UP2/ETH2 MN node240 ↔ Linux/ETH3测试CN暂拟node1。不是运行配置或许可。保留[未来工业CN资料模板](../../config/powerlink-cn-intake.template.json)，目前没有设备也不阻塞软件路线，不猜厂商/型号/XDD或生产PDO。

## 实际构建与回归

构建服务器 `/home/openeuler/build/powerlink-cn-p4a-20261105`，容器`dev_openeuler`。
原生编译器GCC12.3.1/x86_64-openEuler-linux，交叉工具链Arm GNU14.3.1/aarch64-none-linux-gnu。
全程只编译、安装到**新输出目录内**和readelf检查；未运行任何一个CN二进制（连`--help`也未运行），未连接板卡/串口或改变网络。

| 目标 | 最终ELF | CN静态库 | 独立复编 |
| --- | --- | --- | --- |
| x86_64 | 271408B，`d9696287…` | 453338B，`3d7dfd7b…` | ELF及.a均逐字节一致 |
| AArch64 | 340536B，`bc53889d…` | 420074B，`80a19f0d…` | ELF及.a均逐字节一致 |

[native双目录日志](native-final.log)、[AArch64双目录日志](aarch64-final.log)均EXIT0；每个最终目录及repro目录的build-report记录完整SHA，ELF头/动态依赖/版本需求另存。
`aarch64-final`需要GLIBC_2.38等符号；这是readelf静态观测，不是已核实板卡运行库兼容或已经在板卡运行。
raw-socket无需pcap，但仍是Linux用户态调度/网卡路径，不能据此验收1ms、工业抖动或实时性。
上游demo默认NodeID1、初始cycle50000us；候选0x6000:1/0x6200:1是8位过程量，当前映射默认零，**未生成MN/CN匹配配置**，不把这些默认值当已评审联调参数。

首次[native](native-first.log)/[AArch64](aarch64-first.log)均编译成功；首次[native独立比对](native-repro.log)EXIT1：ELF相同但.a归档头时间戳不同。
[诊断](archive-diagnosis.log)保留；新增显式`ar qcD/ranlib -D`及固定构建epoch/路径映射后，重新创建四个最终构建目录，双架构ELF和.a均一致。首轮产物/失败日志不覆盖，最终以`*-final`为准。
上游编译警告（如demo接口名strncpy边界、旧CMake策略等）原样记录，未声称零警告或可直接生产使用。

Windows[330项](windows.log)/Linux[330项](linux-tests.log)通过，原312+新增18，涵盖CDC截断/长度/条目界限/重复顺序/嵌套scope/不覆盖输出及Linux构建隔离边界。
验证器还复核历史11月4日P3j-v2实板自动闭环，但**不是本轮新硬件执行**。

## 换机复现

在已有固定构建容器/工具链的Linux工作目录执行，输出路径必须不存在：

```bash
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_linux_cn.py /tmp/new-cn-native
python3 stages/stage07-peripheral-partition/build/build_m7_powerlink_linux_cn.py /tmp/new-cn-aarch64 \
  --aarch64 --cc /home/openeuler/build/tl3572-2oo3/toolchain-14.3/bin/aarch64-none-linux-gnu-gcc
```

这两条只构建，**不要运行生成的demo**。新机器的SDK/工具链仍使用项目既有固定Docker/源代码复现方案，未另打SDK包或重编UP2。
只做离线证据/产物/330项回归/1355源文件与Linux补丁复核：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_cn_p4a_checkpoint.py \
  /tmp/new-cn-source-check --expected-commit <当前检出提交>
```

新清单继承上阶段820项及后验日志，原源码/固件/证据保持旧SHA，仅memory/stage索引滚动。
GitHub全新拉取和服务器delivery的后验日志另归档，以最终报告为准；这两项是源码/已构建产物审计和回归，不冒充在GitHub检出后再次完整交叉编译。

## 下一步（不等待采购）

先实现并离线验证**有CN的独立有界MN入口**及对应decoder，补节点/CFM/SDO事件、MN+CN配置和过程映像交换、正常RX/PDO接收判据、身份/数据序号/安全退出证明。
软件CN demo仍不受限，须先加接口白名单、进程身份/启动结束预算和安全退出包装，核对目标Linux运行库；当前不能直接将它上线或与旧P3j连跑。
完成上述门槛后，再另问一次ETH2↔ETH3隔离软件CN互测许可。本轮没有新硬件授权请求，也未使用旧窗口。
按karpathy-guidelines，仅新增独立工具/新解包构建，未放宽旧P3j判据；现阶段不宣称MN↔CN互操作、PDO/SDO、持续运行或真实工业从站验收。
