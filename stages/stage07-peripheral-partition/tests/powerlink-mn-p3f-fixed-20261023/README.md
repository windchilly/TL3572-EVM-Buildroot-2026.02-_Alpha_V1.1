# P3f：状态查询栈修复、完整MN栈GsOff实板门槛通过

2026-10-23，首次故障后用户另行明确批准“清理、修复并复测”。
**修正版一次实板通过：initialize/prepare/128次GsOff process/stop/exit，安全归还Linux，无整板重启。**
不执行NMT reset/start、不发测试或CAN/串口帧、不改正式固件/M6/DT/开机配置。不是MN/CN运行或实时性验收。

## 恢复与修复

[旧故障/原始证据](../powerlink-mn-p3f-hw-20261023/README.md)和首次b00cdf候选均保留，不把失败覆盖成成功。
`restore_powerlink_mn_dormant_fault.py`只接受精确旧ELF/boot/异常/未提交命令COLD缓存/零lease，
并必须独立证明CPU4/5已OFF，才清理失效管理表/端点、重绑LinuxETH2、确认两端full、移除hold。
[实际恢复日志](../powerlink-mn-p3f-hw-20261023/restore-exact-dormant-fault.log)。这不是通用unsafe恢复工具，当前共享日志已进入新boot代数，不能再次自动套用。

根因中的明确缺口是TTY栈预算：P3f快照增长使输入帧1712B，已知日志链下界4336B超过默认4096B线程。
将`Rk3572PowerlinkInput`的完整快照与回复缓冲移到函数静态BSS，`inputActive`覆盖缓存拷贝、格式化、日志、发送全过程。
只支持既有串行TTY consumer；意外重入不覆写活动回包、不修改邮箱、不二次RPMsg发送。IRQ锁只保护claim/copy，不包格式化/send。
没有扩大所有线程栈、删诊断功能或改MN核心；旧timer/PHY/EDRV/CAN/FD/串口功能保留。

[最终ELF栈预算](stack-budget.json)：输入帧320B，关键路径2944B+显式1024B预留=3968B≤4096B，预留之外余128B。
审计验证8个实际函数的SP分配与调用边，直接挂入最终P3f ELF审计，旧4336B候选会被拒绝。
这是固定整数/字符串状态日志路径+预留的回归门槛，不是所有路径/浮点格式/异常/IRQ最坏栈证明；仍需生产栈峰值和长稳验证。

## 实板结果

[完整原始日志](board-test.log)、[板端结果JSON](board-result.json)、[实际输入SHA](board-input-sha256.json)、
[前预检](board-preflight.log)、[最后预检](board-final.log)、[停核后私有缓存](private-snapshot.log)。

| 项目 | 实测 |
|---|---|
| 真实完整栈 | IDLE初始化→PREPARED→128次process→停止→COLD退出；rc0/clean1/stage5 |
| NMT/事件 | 实际GsOff，processes128/events0；不reset/start |
| EDRV | MAC0xc003/100M half，RX0/TX完成0/TX描述符使用0，背景过滤drop1 |
| 错误 | rxerr0/txerr0/DMA fatal0，异常cause/ELR/ESR0 |
| ETH停止 | MAC/TX/RX/SWR/MACIRQ/DMAIRQ六回读0，lease0/0 |
| Timer | IRQ0/回调0，timer lease0/0；24MHz、CNTP_CTL2，PPI30 enabled/pending/active0 |
| 保留OS资源 | CNTV_CTL1、priority30=160/priority27=0、group/config保持；tick88→2579 |
| 最终Linux | 两UP Offline、CPU4/5 PSCI OFF，ETH2/ETH3恢复100M full/AN on，临时client/hold/端点移除 |

物理PHY准备约耗数秒，tick变化包含PHY协商，不是128个实时周期/1000us调度证明。本轮没有重测定时器IRQ精度。
TTY/listen实际分配栈均4096B未扩大；私有DRAM是停核后缓存，不替代此前真实硬件停止回读与Linux重绑定的独立证明。
CAN/UART绑定和寄存器、管理ETH1=eth0/192.168.2.141地址路由、Linux CPU集合保持。
boot_id6974ac40-f3a2-4433-a5b8-11ec4318248f、micad PID328/NRestarts0/active在恢复与复测全程不变；没有打开COM7或重启整板。

## 软件回归与构建

[首次/最终原生](native-first.log) / [最终](native-final.log)、[Windows](windows-tests.log)：
真实完整栈29场景+真实累计邮箱4场景（新增重入）、7项栈预算Python（含旧真实1712B回归），Windows/Linux各136Python通过。
原100轮完整栈12800process/1600alloc-free、P3e/P3d/P3c/P3b/P0-P3a、累计parser/18生命周期/3codec回归通过。
原生硬件边界仍mock；没有ASan/UBSan，旧M6 endian/RWX告警保留。

Docker `dev_openeuler`构建根`/home/openeuler/build/powerlink-mn-p3f-fixed-20261023`。
`software`/`software-repro`明确复制已验证旧P3f软件根，9旧对象非本轮重编核心；两全新累计源树`UniProton-first/repro`真实复编。
[构建1](candidate-first.log)、[构建2](candidate-repro.log)、[双根比对](repro-comparison.json)、
[审计1](mn-probe-audit.json) / [审计2](mn-probe-audit-repro.json)。两runtime逐字节一致，不承诺不同DWARF路径的ELF完整字节一致。

实际[新UP2候选](candidates/tl3572-m7-powerlink-p3f-up-b.elf)，1,186,944B，SHA256：
`47c0bb5425b9121b3db83572f47d684179962d226c1850123ecb19d1b662fda4`。
UP2runtime630100B/SHA `518b2e7315a816ebb195532561a07bcba7031f9920745c34bac426a3b3dde4ff`；
image/BSS2159392B/8MiB、FSC512KiB、页表10/16；UP1runtime仍360716B/d4d80d02...、页表9/16，本轮未运行UP1。
596旧全局函数保留、最终U0/LSE0、125条旧FP/SIMD无新增；不是全ELF无FPU，也不是实机堆峰值证明。
正式两份ELF仍8bfb824b.../627545f5...，未覆盖稳定固件。

## 换机复现

先恢复[固定完整M6源码/SDK/工具链和摘要Docker](../../../../repro-inputs/rk3572/README.md)，按
[P3f软件构建入口](../powerlink-mn-p3f-20261023/README.md)的全新software/UniProton根执行当前
`build_m7_powerlink_passive_mn.sh`与`build_m7_powerlink_mn_probe_candidate.sh`；后者现强制执行栈预算审计。
运行`run_powerlink_mn_probe_native.sh`和所有`test_*.py`，第二根用`compare_powerlink_p3f.py`核对runtime。
换机必须从完整源码构建软件根，不依赖本轮复制目录。SHA256SUMS按本轮源/配置/脚本/候选/原始证据列出，历史清单到历史commit核对。

板端输入与候选在`/root/m7-powerlink-mn-p3f-fixed-20261023`，临时配置`up-b-m7-plk-mn-probe-fixed.conf`、AutoBoot=no。
实际文件列表/哈希见board-input-sha256.json，另有仅读缓存的read_powerlink_mn_snapshot.py。
固定host hold模块SHA b071d434...匹配6.12.69-gf1b67c293213，源码/构建脚本已归档，本轮复用未重编。
后续复测仍须新的隔离移交许可；获准且原两UP Offline/物理OFF后才运行
`python3 run_powerlink_mn_probe.py --confirm-isolated-gsoff-lifecycle --sha256 实际新候选SHA`。
服务器`delivery/`保存本轮输入与证据，GitHub后验日志不列入自身清单；最终上传状态以最终报告为准。
下一步是受控NMT reset/停止的软件入口与状态迁移，物理MN帧/CN/PDO/SDO/真实伺服仍未获准或验收。
