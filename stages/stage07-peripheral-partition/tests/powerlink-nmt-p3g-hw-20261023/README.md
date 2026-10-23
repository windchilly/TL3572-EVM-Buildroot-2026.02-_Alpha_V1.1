# P3g：单次受控 NMT 实板失败与保留现场（2026-10-23）

结论：**FAILED / 未达到 NotActive / 未执行 SwitchOff / 未安全退出或归还 Linux**。
不能把原生软件通过、驱动收发通过或本页离线回归写成 MN 实板通过。
P3f 修正版的 GsOff 生命周期仍是最近一次完整栈硬件通过基线。
用户随后明确批准一次重启恢复和软件修复；已经重启一次并只读确认恢复，见下文。
下述“保留现场”是重启前证据，不是当前仍占用资源。

## 授权与实际执行

用户明确确认 ETH2↔ETH3 仍为板上隔离网线回环，允许固定 P3g 候选单次
`软件 SwReset → NotActive → 立即 SwitchOff → 静默退出/归还 Linux`，可能产生有限协议帧。
不允许持续 MN、真实 CN/伺服、专用测试帧、CAN/UART 数据、正式固件/开机配置变更或自动重启；
未知状态保留资源、不重试。本窗口已经用完，不得重新执行 runner。

执行前源码提交：`7281943595b082b408933771e18d4c123d7e3b3a`。
临时根 `/root/m7-powerlink-nmt-p3g-20261023`，客户端 `up-b-m7-plk-nmt-probe`，AutoBoot=no。
`ATTEMPTED` 永久单次标记已创建；只提交了一次 `PLK nmt-probe`，其后的重复记录是只读状态轮询。
候选 SHA256：`85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e`。

- [预检](board-preflight.log)：原两实例 Offline/CPU4、5 OFF，Linux ETH2/ETH3 100Full/ANon，管理口和工控空闲状态符合门槛。
- [18 个实际输入 SHA](board-input-sha256.json)：SFTP 上传后逐个读回校验；包含真实候选、ABI JSON、runner/依赖/conf。
- [原始全过程](board-test.log)、[实际结果](board-result.json)：submitted=true，passed=false，cleanup=false；没有停核私有证明。
- [稳定故障缓存](failed-cache.log)：seq=done=1，owner=6，rc=4，clean=0，stage=3，stackError=5。
  resetSubmitted=1，offSubmitted=0，resetLoops=4，offLoops=0，reached=0。
  初始化 IDLE、准备 PREPARED 成功；停在 NMT ResetCommunication `0x39`，最终 FAULT。
  堆栈异常 cause/ELR/ESR 均为0；不是此前 TTY 栈异常或 MMU 页表容量故障的再次出现。
- 缓存 RX/TX/TX 描述符使用、硬件错误、定时 IRQ/回调均为0；没有专用测试/CAN/UART 发送。
  这不是独立全线抓包证明，不能据此承诺物理线路绝对无帧。

## 原因：真实 RTOS 共用堆不足

[只读分配器/PDO 元数据](allocator-platform.log)与[实际 AArch64 编译几何](pdo-memory.json)相互印证：

| 项目 | 字节/数量 |
|---|---:|
| FSC 配置 | 512 KiB |
| 分配器可用总量 | 524256 B |
| 故障时已用/峰值 | 375336 B |
| 总剩余 | 148920 B |
| 实际 RX / TX PDO 通道 | 40 / 40 |
| 映射对象大小 / 每通道上限 | 16 B / 254 |
| 下一块 TX PDO 映射表 | 162560 B |
| 不含分配器开销的最小缺口 | 13640 B |

`pdouInstance_g` 的 RX/TX 通道表和 RX 映射表非 NULL，TX 映射表 NULL；PDO 共享内存尚未建立。
真实 `pdou.c::allocatePdoChannels()` 的分配顺序与这些字段一致，TX 映射表请求
`16 × 40 × 254 = 162560B` 已大于全部剩余堆，不仅是碎片问题。

`test_powerlink_pdo_memory.c` 只编译、不链接进固件，直接包含固定上游的私有类型；
`audit_powerlink_pdo_memory.py` 用固定14.3交叉工具链核实10项大小/偏移
`16,254,254,16,576,512,512,516,536,544`，避免仅凭手工推算字段位置。
[Linux 实际编译/169项回归](linux-offline.log)保留完整输出。

原生 NMT 测试使用宿主机 malloc，没有模拟 RPMsg/MICA/RTOS 共用 FSC 堆占用；
此前 GsOff 不会进入 reset 阶段的新 PDO 映射分配，因此此前通过与本次不足并不矛盾。
这是新增路径的动态内存预算缺口，不是所有旧外设功能突然失效。

原始 critical error 被 `m7_mn_process()` 的后续 fault(kErrorInvalidOperation=5)覆盖；
不能把缓存5当作最初 PDO 返回码的直接采样。源码 NULL 分支返回 kErrorPdoInitError，
本次定位依赖分配器/指针证据与真实布局/源码分配顺序，而非保存了原始错误。
后续应保留 first-error、建立真实 RTOS 堆预算/峰值测试，再决定完整 OD 所需堆容量；
不能为了通过测试悄悄裁减通道。**本轮尚未修改固件或扩大内存池。**

## 保留现场：没有执行清理

[只读系统清点](retained-inventory.log)：

- boot ID `6974ac40-f3a2-4433-a5b8-11ec4318248f`，micad PID328、NRestarts=0、active。
- 原 up-a/up-b Offline；临时实例仍 Running，CPU5 的 RPMsg 可响应，CPU异常缓存为0。
- ETH2 的 Linux GMAC1 驱动保持解绑、eth1 不存在；`m7_eth2_power_hold` 仍加载。
- ETH3/eth2 link=yes、100Half，管理 ETH1/eth0 `192.168.2.141/24` 与路由不变。
- ETH lease=2、timer lease=1；尚未执行的 stopped/timerFinal 全零字段只是未初始化，**不是停止证明**。
- CAN0..3 DOWN，systemctl failed=0，内核 taint4096 未出现 Oops128。

故障后只读取私有 DRAM 的小范围缓存/元数据，没有访问控制器 MMIO或遍历堆；
没有 stop/rm、强制 CPU_OFF、重绑 Linux、去 hold、重试或重启。
不能把本次现场套进旧 CASAL/TTY 故障恢复工具（候选/异常/lease/CPU状态均不符）。
整板恢复/重启必须获得新的用户授权。该候选是 terminal FAULT，不能热修后原地重投。
未打开 COM7。M6、DT、kernel、正式两 ELF、开机配置未改变。
本地正式累计 UP-a/UP-b SHA 保持 `8bfb824b...` / `627545f5...`；没有替换到板卡 M6 路径。

## 后续新授权：一次重启恢复（不是 NMT 复测）

用户明确回复“允许重启恢复并继续软件修复”，范围不含新候选部署/硬件复测。
[一次 reboot 原始日志](authorized-reboot.log)记录了重启前精确窗口/boot核对，只有一次 systemctl reboot。
新 boot ID `cd4f03d6-005d-473d-b6ce-0cc745314a08`；CPU4/5 PSCI OFF，原两实例 Offline，
临时 client/端点已消失，hold未加载，Linux ETH2/3恢复100Full/ANon/linkyes，failed服务0。
[最终只读复核](recovery-verification-v3.log)确认驱动恢复和板端原M6配置所指固件与仓库M6一致：
UP-a `9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8`，
UP-b `3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4`。

初次复核脚本猜错固件/配置路径，随后又错误地以本地M7候选哈希核对板端M6文件；
失败日志如实保留为 authorized-reboot.log 末尾和 recovery-verification.log / -v2.log。
查阅 M6 实际配置后修正为 `/etc/mica/tl3572-up-*.conf` 的 ClientPath，-v3完整通过。
这些都是重启后的只读检查失败，**没有再重启/清理/加载候选**。
板端失败输入、board-result.json和ATTEMPTED仍保留；原失败结果不改写成PASS。

## 独立的验收器修正（离线，未用于清理现场）

发现 `powerlink_nmt_checks.py` 原来把 raw CurrentEL 错当成 EL 编号，要求1；
BSP 实际读取原始寄存器，EL1 为4，故障缓存和历史成功缓存均为4。
本次修正为4并新增拒绝1的双快照回归；[Windows169项](windows-offline.log)和Linux169项通过。
这个错误不是本次 stage3 分配失败的原因，停止验收器尚未被调用。
没有把修正后的文件覆盖板端原输入或用它触发清理；原18项 SHA 和原提交保持可追溯。

## 离线复现与归档

先按 [P3g 软件构建](../powerlink-nmt-p3g-20261023/README.md)恢复固定源码/工具链，**不要执行板端 runner**。
在 stage07 目录：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/audit_powerlink_pdo_memory.py \
  /path/to/p3g-software/source/openPOWERLINK_V2-2.7.2 /path/to/toolchain-14.3 \
  tests/powerlink-nmt-p3g-hw-20261023/allocator-platform.log /tmp/pdo-memory.json
```

后续[P3h清单与软件修复](../powerlink-nmt-p3h-20261023/README.md)纳入本次原始硬件证据；旧清单回到各自历史提交验证，未被重生成。
`verify_powerlink_p3h_checkpoint.py`验证当前精确清单、失败状态、内存几何、原18项输入和175项测试，
并实际解包1355文件/应用0001–0007补丁；它没有板卡访问或恢复路径。
原板端18输入可从 `7281943595b082b408933771e18d4c123d7e3b3a` 取回；
当前只有 checker 的 CurrentEL 校验与其旧 SHA 不同，验证器明确从 Git 历史核实这一个原始输入。
后验 GitHub 验证日志不纳入自身清单；GitHub同步及服务器交付状态以最终报告为准。
只读诊断构建根 `/home/openeuler/build/powerlink-nmt-p3g-hw-20261023`；完整交付与后续修复存入独立
`/home/openeuler/build/powerlink-nmt-p3h-20261023/delivery`，不覆盖旧 P3g 软件/runner 目录。

后续软件修复在独立 P3h 检查点进行；新候选单次实板复测仍需新授权，不能沿用已消耗的窗口。
