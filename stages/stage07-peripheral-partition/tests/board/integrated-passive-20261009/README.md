# 统一固件被动启动测试与故障定位（2026-10-09）

结论：`ORIGINAL INTEGRATED UP1 BOOT FAIL / ROOT CAUSE IDENTIFIED / NOT FIXED / PHYSICAL TEST PAUSED`。
用户要求继续UP外设测试，随后明确“接线已改变，先不要发送”。本轮没有执行任何M7 run，
没有向CAN/RS-232/RS-485发送工业测试数据，也没有解绑控制器、重启、刷写或修改DT。
仅通过临时AutoBoot=no实例测试被动启动、日志、RPMsg虚拟诊断/echo和启停。

## 正式固件结果

测试输入为固定提交`17024db864070b655dc94a4530ae59baec3fb6c7`的两份统一ELF，
源码、ELF和[旧合并记录及65项清单](../integrated-20261009/README.md)均不回写。

- UP1 SHA256：`d22bdf200c326e2727d4c9ff9f19e4aa46c38727b3b7b7dedc7f33503fbf1581`。
- UP2 SHA256：`1a4ece0cff536cfe5f796b1aecc843fc04b7ffb3ad5243ca094dba99b84fa622`。

`run-01-original.log`和`run-02-original.log`两次均进入CPU4、调度任务并打印integrated passive ready，
但15秒内没有RPMsg TTY，随后安全停止/移除临时实例。两次均在UP1阶段失败，
正式UP2尚未在该成对执行器中启动，不从诊断版或静态分析推断正式UP2实机PASS。

被动执行器为`../run_integrated_passive.py`：严格只允许M7 status、M7 unsupported，保留普通M6 echo；
拒绝任何M7 run，包括拼接多命令。逐轮核对零工作计数、启动日志、外设资源、micad及CPU OFF。
脚本自身不写CRU/IOC/GIC；固件启动仍有正常GIC CPU接口/SGI初始化，不是完全无MMIO的启动。
目前原固件会先失败，默认4对启动/停止的计划未完成，不能记为四轮PASS。

## 根因与直接证据

1. `audit_integrated_mmu.py`读取ELF真实映射和链接符号。UP1需要9张4KiB页表（36KiB），
   链接区`g_mmu_page_begin..end`仅32KiB；UP2需要8张，刚好占满32KiB。
2. UP1按原映射顺序在`0x26090000`申请第9张页表，`mmu_create_table`返回NULL，
   `mmu_init`返回错误。`Start`反汇编显示BL mmu_init后直接B OsResetVector，未检查返回值。
3. 停核后读取实际页表：8页均已有PTE，GIC/CAN/UART已部分建表，但CRU/IOC和最后log映射缺失，
   与上述分配失败位置完全一致。异常现场TTBR/TCR/MAIR为0，SCTLR=`0x30d00800`、M=0，MMU未开启。
4. 异常ELR=`0x7b202b04`为`metal_io_init+0x108`的`str q28,[x1]`，FAR=`0x7b2563a8`，
   ESR=`0x96000061`（同EL写入数据中止、DFSC=0x21对齐错误）。未启MMU情况下，这次非16字节
   对齐的128位写触发异常，RPMsg创建未完成。

证据：`mmu-budget-audit.json`、`mmu-startup-source.log`、`fault-disassembly.log`、`postmortem-up1.json`。
`g_mmu_ctrl`在后续BSS初始化中被清零，不能把残留的0值作为mmu_init时期的分配计数；
本结论依据真实PTE、异常寄存器、ELF映射和源码分配路径交叉验证。
审计仅支持当前4KiB、32位VA/L1起始、L2/L3对齐映射，不是通用ARM MMU仿真器。

## 仅用于诊断的实验版本

另建容器源码树`/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-passive-diag-20261009`，
从相同M6基线准备统一树后，仅应用本目录`diagnostic-hooks.patch`，增加6条启动诊断打印。
没有覆盖正式源码、原两ELF、M6固件或配置。构建日志`build-diagnostic-final.log`，
第一次补丁hunk计数错误保留为`build-diagnostic-first.log`，修正后才成功编译。

诊断ELF哈希（非正式交付）：

- UP1：`b06e93b872fd5dde5c9b572149e09ef930d4368dd58e02cd47da33db7f150ae5`。
- UP2：`6015a2e68207541bb74dcb592d619376869c8ebbdae367148e6a644d6ef6eae9`。

板端独立目录`/root/m7-integrated-diag-20261009`，配置ClientPath指向此处、AutoBoot=no。
实验执行器只把原被动脚本ROOT和HASHES改为诊断目录/上述哈希，其余逻辑不变。
命令`python3 run_integrated_passive_diag.py --cycles-per-order 1 --echo-count 1`，
`run-01-diagnostic-only.log`记录两对启动、两种停止顺序，每UP累计2次451字节虚拟echo，
M7 status/非法命令与第一路停止后的幸存实例查询通过，外设工作计数一直0。
两轮都为UP1后UP2启动，尚未覆盖反向启动或长时间压力。

但诊断打印把shm_device从`0x7b256360`移动到`0x7b256418`，同一ops写入目标从
`0x7b2563a8`变为16字节对齐的`0x7b256460`。页表预算仍32KiB，启动错误路径未改；
诊断版的局部通过只说明地址布局可掩盖故障，不是根因修复或集成PASS。
不把诊断ELF作为新的交付固件；提交完整诊断补丁与构建步骤，可在固定基线复建。

## 复查方法

无板卡即可运行（仓库需git lfs pull取得正式ELF）：

```text
python stages/stage07-peripheral-partition/tests/audit_integrated_mmu.py
python -m unittest discover -s stages/stage07-peripheral-partition/tests -p "test_*.py" -v
```

原固件页表审计应返回exit 1，UP1 fits=false；单测39项通过只证明执行器/审计等逻辑，
不是固件启动通过。旧verify_integrated_elf只查映射声明，未查实际建表预算，旧PASS不能覆盖此失败。
诊断版复建：按[构建入口](../../../build/README.md)准备全新统一树（固定17024db输入和M6库），
git apply本目录diagnostic-hooks.patch后运行同一build_m7_integrated.sh。
构建路径影响ELF调试段hash，不跨路径承诺完整ELF逐字节一致。

`read_postmortem_up1.py`只读停止后内存，地址及结构偏移仅适用于上述正式UP1 ELF；
运行前必须核对hash、CPU4/5 OFF且没有启动其他固件覆盖残留。它按整页读取避免/dev/mem
的未对齐尾部访问。不能拿它解析未来修复ELF或运行中的核。
`inspect-startup.sh`、`inspect-fault.sh`在现有构建容器只读导出源码/反汇编；
首次取证脚本因工具链没有elf-addr2line而终止，保留`fault-inspection-first.log`，
移除该非必要命令后成功输出完整反汇编。

## 安全结束状态与待办

`final-state.log`确认原up-a/up-b Offline、CPU4/5 PSCI OFF、临时客户端和ttyRPMSG已清理。
所测六控制器Linux绑定与CRU/IOC/外设SPI快照前后一致，micad PID311 active/NRestarts0，
failed units=0，ETH1正常，boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7`未变。
已知另一处MCS create/rm fd泄漏仍存在：本轮51→53→55→57，不能宣称全程fd无漂移。
诊断两个start/stop周期内部离线fd集合未漂移，与create/rm遗留问题分别记录。

下一步等待用户指示修复：建议仅统一目标增加页表预算（至少36KiB，建议64KiB留余量）、
启动检查mmu_init返回值，并把SCTLR.M=1与全部实际PTE作为启动验收项；
之后复编两份统一ELF、独立树复现并做无工业发送的双实例启动/诊断/两种启停顺序回归。
不要只对齐shm_device或保留诊断打印当作修复。物理测试须重新确认接线后再启动。
SARADC/ETH2未加入、FD2/4仍SKIPPED，持续协议、并发物理收发、实时性、持久DT/冷启动及M7.0均未验收。

本目录SHA256SUMS独立固定当前证据/脚本与正式输入；不改旧合并清单或历史原始证据。
