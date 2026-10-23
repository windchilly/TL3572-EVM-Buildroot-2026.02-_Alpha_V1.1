# P3f 首次硬件窗口：状态查询失败，联合生命周期尚未执行

2026-10-23，用户确认隔离ETH2↔ETH3仍在，批准一次临时联合ETH2/CNTP的完整栈GsOff检查。
**本次未通过：首次只读`PLK status`回包超时，`PLK mn-probe`尚未提交，128次栈处理未执行。**
没有发NMT reset/start、测试帧或工控数据，没有更改正式ELF/M6/DT/开机，没有重启或自动重试。

## 当前现场（需要后续明确处理）

[原始测试日志](board-test.log)、[只读检查](board-inspection.log)、[异常与物理核状态](cpu-exception.log)、
[保留现场快照](board-retained.log)、[机器摘要](failure-summary.json)。
runner因未知状态在写最终JSON之前退出，故没有board-result.json；空的下载占位文件已撤除，不能当作结果报告。

- 候选启动/MMU通过，真实页表10/16。共享日志boot4/seq160–172；最后只有COLD/seq0/cmd0的状态日志，无MN BEGIN/PHY/CNTP初始化。
- 私有DRAM缓存seq/done/cmd均0、MN COLD/owner0/processes0/events0、g_ethLease0；运行时DRAM可能陈旧，不能单独当停核证明。
- 异常cause7/task9，ELR/FAR=0x26262626、ESR=0x8a000000/EC34（PC alignment）。
- 独立内核PSCI检查已多次确认CPU4/5均OFF：CPU5由异常流程自行下线，不是我们强停。MICA临时管理表仍写Running，不能据此认为CPU仍运行。
- runner在未知状态按规则保留临时client、ttyRPMSG0、Linux ETH2解绑与共享电源/根时钟hold；没有stop/rm/rebind/rmmod。
- Linux ETH2/eth1目前不存在，ETH3/eth2无link/DOWN。ETH1/eth0管理192.168.2.141/路由正常，CAN四口DOWN。
- boot_id仍6974ac40-f3a2-4433-a5b8-11ec4318248f、micad PID328/NRestarts0/active、Linux CPU集合0-3,6-7不变。

目前保留状态不是“恢复成功”。不得直接运行旧CASAL专用恢复工具，也不得跳过状态查询去执行MN命令。
已向用户询问新的清理/修复/新候选一次复测许可；未收到回复前不执行这些后续操作。

## 栈预算超限证据

[实际TCB/栈边界](task-stack.log)、[线程身份](thread-identities.log)、
[输入/线程反汇编](stack-depth.log)、[默认线程栈/旧帧对比](stack-allocation-proof.log)、
[日志调用链](printf-stack-proof.log)、[安全格式化封装](log-stack-wrapper.log)。

实际TCB stride800/max16：任务8是rpmsg_tty_task，任务9是rpmsg_listen_task，两者均4096B；owner任务6独立32768B。
P3f完整快照1008B，使Rk3572PowerlinkInput自身帧从P3e的0x470=1136B增加到0x6b0=1712B。
这不只是输出文字长了，也不是页表不够；状态查询即复制所有累计诊断结果并在同一路径调用格式化日志。

| 实际调用链 | 帧字节 |
|---|---:|
| rpmsg_tty_task | 576 |
| Rk3572IntegratedInput | 352 |
| Rk3572PowerlinkInput | 1712 |
| PRT_Printf | 176 |
| UpLogVprintf | 608 |
| vsnprintf_s | 80 |
| SecVsnprintfImpl | 80 |
| SecOutput | 752 |
| 已知下界合计 | 4336 |

4336B已超过4096B，还未计更深叶函数、线程入口或中断上下文。相同已知链的旧P3e下界为3760B，
所以旧版本短样本成功不覆盖新快照造成的576B增长，也不是旧版本已证明有充分栈余量。
原生测试使用宿主大栈，最终ELF审计此前只检查镜像/MMU/ISA/符号，未检查此调用链栈上限，这是测试覆盖缺口。

静态预算超限已确认，与本次状态查询异常相符；“具体哪个写越界、如何导致邻接listen线程PC损坏”尚未直接追踪，
需要修复后受控复测或更细栈跟踪验证。栈底哨兵前64字节仍未变，不足以反证栈帧/深层访问没有越界。
修复应压缩/移出状态查询的完整快照临时副本，并为最终调用链增加预算回归；不能只继续加诊断而忽略TTY线程栈。

## 输入和复现边界

实测候选为[上一软件检查点归档ELF](../powerlink-mn-p3f-20261023/candidates/tl3572-m7-powerlink-p3f-up-b.elf)，
SHA256 `b00cdf67837d3359488385f4709fa1a162cd4ea6a791855c6f9708c1411992c1`；未修改或重编该候选。
[板端实际输入哈希](board-input-sha256.json)是上传的runner/helpers/conf/ELF逐字节回读校验。
本轮没有源码修复，原[129项软件测试/双新树构建记录](../powerlink-mn-p3f-20261023/README.md)不变，但不能把软件通过写成硬件通过。
首次反汇编命令用了不存在的cross addr2line，以及错误的rpmsg_service路径，失败原始日志均保留；
随后使用系统addr2line、真实`src/component/mica/rpmsg_service.c`与最终ELF反汇编取得上述数据。

复建仍按上一软件检查点从固定完整M6/工具链/摘要Docker构建；**本候选不应再次上板**，先修复栈预算。
板卡输入保留`/root/m7-powerlink-mn-p3f-20261023`，无AutoBoot配置；构建服务器原根不动，
本轮源码引用/证据按本目录SHA256SUMS另归档到`powerlink-mn-p3f-hw-20261023/delivery/`。
历史清单到相应历史commit核对，GitHub后验日志不列入自身清单，上传状态以最终报告为准。
