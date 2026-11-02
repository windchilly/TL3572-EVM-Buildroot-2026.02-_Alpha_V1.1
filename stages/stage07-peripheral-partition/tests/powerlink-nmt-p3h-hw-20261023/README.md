# P3h：单次 NMT / 真实 FSC 堆 / 安全归还实板通过（2026-10-23）

结论：**PASS，仅限一次有界 `SwReset → MN NotActive → 立即 SwitchOff → GsOff → stop/exit`**。
这次修复越过了 P3g 的真实共用堆不足点；不代表持续 MN、真实 CN、PDO/SDO 通信、周期性能或长期无泄漏通过。
没有修改/重编候选、正式两份固件、M6/DT/kernel或开机配置。

## 授权、输入与单次窗口

用户新确认：“隔离回环仍在，允许一次 P3h 受控复测”。ETH2↔ETH3 为板上隔离网线回环。
范围允许临时转交 ETH2/CNTP、有限协议帧、读取真实堆和安全归还；不含持续 MN/CN、专用测试帧、
CAN/UART 数据、自动重启或未知状态重试。

- 执行前提交 `5830ecf8048e029ef9fae3b3bcc47a5386587c3f`；预检重新核对原603 SHA与21固定输入。
- 候选 `ccfba235f8f3bcc79ab0c2a0e603b2d9cc01a7f3785985566660fb1672882ea8`，1196696B。
- 新根 `/root/m7-powerlink-nmt-p3h-20261023`，临时 client `up-b-m7-plk-nmt-p3h`，AutoBoot=no。
- [21个实际上传读回回执](board-input-sha256.json)与[软件准备清单](../powerlink-nmt-p3h-runner-20261023/runtime-inputs.json)逐项一致。
- [ATTEMPTED原文](ATTEMPTED.txt)保留永久单次标记，窗口已消耗，**不得重跑该入口或删除标记**。
  旧P3g目录、标记和失败结果未改变。
- [只读预检](preflight.log)、[原始全过程](board-test.log)、[板端原始结果](board-result.json)、[只读后检](postflight.log)。

## 实际结果

一次 `PLK nmt-probe`：seq=done=1，reset/off各1次，resetLoops=5/offLoops=1，
实际达到 `0x21c`（MN NotActive），rc=0、clean=1、stage=6，最终 state=COLD / NMT=GsOff。
总 process=6、events=6、lastError=0；完整40 RX/40 TX PDO通道及254映射配置保留，没有裁减OD。

| 真实 FSC 项目 | 启动后 COLD | 完成并停核后 |
|---|---:|---:|
| 池配置 / 分配器总量 | 1048576 / 1048544 B | 相同 |
| 已用 | 37520 B | 38584 B |
| 峰值 | 37520 B | 543648 B |
| 当前可用 | 1011024 B | 1009960 B |
| 峰值余量 | 1011024 B | 504896 B |

初始可用大于767888B门槛；实际峰值余量大于256KiB门槛。
这是实机FSC计数，不是前一宿主模型的636816B峰值。前后已用差1064B如实保留，
包含RTOS/RPMsg背景分配，**单轮不构成严格无泄漏证明**；也没有堆遍历、碎片最坏值或长稳测试。

## 停核与资源证明

只有NMT/RPMsg完成及初始堆合格后执行一次临时client stop；独立PSCI确认CPU4/5 OFF后，
读取1504B私有缓存、真实FSC、异常缓存及实际TTY/listen线程栈各4096B，与RPMsg一致才清理。
[停核后的只读原始缓存](private-snapshot.hex)为1504B十六进制，SHA256
`39b81245a1ccfbedd2c55868cf2a729286dc08e36ff2c35c28c5184606b9f690`；
[后验采样日志](capture-readonly.log)中独立CPU OFF前后确认，内容与最初停止证明的SHA完全一致。
这是小范围私有DRAM证据，不是Linux再读已归还控制器MMIO。

- UP2运行期自配PHY/MAC为100M半双工；active MAC=0xc003，EDRV轮询，无Linux收发代理。
- RX/TX/描述符使用、rxerr/txerr/fatal、timer IRQ/回调均为0；此最小NMT路径未进行周期通信。
  未做全线独立抓包，不能承诺线路绝对无任何背景帧。
- 停止MAC/TX/RX/DMA/IRQ六回读为0，ETHlease=0，timer lease=0；异常cause/ELR/ESR全0。
- CNTP_CTL最终2，PPI30 enable/pending/active=0，24MHz，raw CurrentEL=4；OS虚拟tick相关字段保持。
- 清除新临时client/端点，重绑Linux ETH2，两端恢复100Full/ANon/linkyes，再卸载hold。
- 原up-a/up-b均Offline，CPU4/5最终OFF；CAN全DOWN、工控寄存器/绑定及ETH1地址路由不变。
- boot始终 `cd4f03d6-005d-473d-b6ce-0cc745314a08`；micad PID325/NRestarts0/active，failed服务0、taint4096无Oops128。
- 板端原M6 ClientPath固件SHA仍 `9c5e55a2...` / `3357eb97...`；本地正式M7仍 `8bfb824b...` / `627545f5...`。
  本次未重启、未打开COM7、未发CAN/UART或专用测试帧。

## 换机复核与归档

2026-11-02继续中断的归档/同步工作；本次不连接板卡。上述硬件证据日期仍2026-10-23，不作为11月2日板端状态快照。
本次[本地离线复核](local-verification-20261102.log)、后验[GitHub新检出复核](github-verification.log)与
[服务器交付复核](server-verification.log)保留完整输出。

软件构建按[P3h完整源码/双根构建](../powerlink-nmt-p3h-20261023/README.md)和
[独立runner/双编译器ABI](../powerlink-nmt-p3h-runner-20261023/README.md)复现。
本轮没有重新编译核心或ELF；复用固定候选，只新增硬件证据与离线证据校验。
203项Python和实际1355文件解包/0001–0007补丁复核不访问板卡。

在仓库根运行（只校验归档，**不会上板或重新执行NMT**）：

```bash
python3 stages/stage07-peripheral-partition/tests/verify_powerlink_p3h_hw_checkpoint.py \
  /tmp/p3h-hw-prepared --expected-commit <当前检出提交>
```

本阶段新 `SHA256SUMS`继承全部源码/配置/旧证据并加入实际上传回执、原始日志/缓存/结果；旧清单不重生成。
GitHub和服务器后验日志不纳入自身清单。构建服务器交付根
`/home/openeuler/build/powerlink-nmt-p3h-hw-20261023/delivery`（Docker dev_openeuler）。
GitHub与服务器实际同步状态以最终报告为准。

下一步是设计并离线验证有界MN运行/安全停机，再单独确认隔离运行窗口，之后接真实CN做发现、PDO/SDO与周期实测。
当前USB/Linux ETH3只是开发对端，不能代替真实CN或实时验收；不自动推进到持续发帧或真实执行器控制。
