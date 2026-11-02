# P3j：UP2 一次性 MN 周期保护与累计候选（2026-11-02）

结论：**生产诊断/owner接入、离线故障回归、双根构建和最终ELF审计通过；未上板。**
本轮仅连接构建服务器，不连接板卡/COM7、不接管ETH2/CNTP、不发物理帧、不重启、不改正式固件或开机配置。
最近硬件基线仍[P3h单次NMT](../powerlink-nmt-p3h-hw-20261023/README.md)，旧窗口已消耗。

## 从P3i宿主策略推进到实际owner路径

新增 `m7_cycle_probe.c/h`，由真实 `PLKowner` 消费 `PLK cycle-probe`，不再由HOST测试手动置FAULT代替保护。
0021的 `M7_POWERLINK_CYCLE_PROBE` 默认OFF，只允许CPU5/显式NMT/1MiB候选；候选启动仍dormant。
没有 `PLK run/start`、任意节点或周期参数，不能持续运行；一次成功/失败后，周期命令都不能在同一boot重投。
旧env及CAN/FD/RS-232/485、timer、PHY、EDRV、GsOff和NMT诊断仍累计保留；默认均不发送。

固定流程：初始化/prepare → 一次SwReset → 自然推进Operational → 有界运行 →
一次stopCycle(FALSE) → 只观察/poll排空 → 一次SwitchOff/GsOff → 一次stop/exit。
完整40RX/40TX/254映射保留；周期1000us，254项CN分配须全0，本阶段不是CN/PDO/伺服业务配置。

| 软件诊断门槛 | 固定值/行为 |
|---|---|
| 总预算 | 8s及4,000,000次process上限，包含prepare返回后的检查 |
| NMT启动预算 | 3s，合法状态单向推进到Operational，拒绝BasicEthernet/倒退 |
| 运行窗口 | Operational后100ms或256次TX完成，先到即收尾；总TX提交不超过1024 |
| 在途TX | 从出现pending/最近一次完成起2ms，不将此前空闲算作排队时间 |
| 无发送完成进展 | PreOp1以后10ms；与pending计时分开 |
| 高精定时 | 24MHz、无丢周期、最大回调迟到不超过500us |
| 排空 | 停调度后5ms内pending归零、总提交不再增加、逻辑timer无armed，再保持1ms安静窗口 |
| 失败 | 首个reason/stackError保留，缓存失败当次的IO/定时器证据；不补发off、不重停、不释放未知资源 |

这些是**本次保守软件诊断策略，不是协议规定的阈值或实板实时保证**。
检查只在调用返回后执行，不能抢占卡死的单次栈调用，不是独立硬件watchdog。
循环不使用1ms TaskDelay模拟周期；占用CPU5的有界owner时间仍须实板测量。
失去合法task/IRQ上下文时，不调用栈或mask其他上下文的CNTP，只保留失败证据和资源。

## 稳定结果区与退出证据

原 `M7PowerlinkSnapshot` 仍1504B；新增独立版本1的 `cycleResult` BSS608B，不塞回旧快照或4KiB TTY栈。
`cycle-status`/新getter在pending/running期间拒绝读未完成结果，完成后可读成功或失败证据。
旧固定SHA的NMT检查器不会因此获得新候选许可；未来必须使用新ELF身份和608B结果的独立板端工具。

新增EDRV查询核对busy软件所有者与pending数一致，不以清掉OWN或擦busy伪造完成；异常返回未知值。
新增hrestimer查询返回真实逻辑armed数量。停止后还要求MAC/DMA六回读、lease、CNTP/PPI30静默及OS tick/GIC相关字段保持。
这仍是软件/候选审计；本轮没有实际CPU OFF后缓存、FSC堆峰值或硬件停止读回。

## 真实原生回归与失败记录

[最终生产函数18场景+owner4场景](linux-final-fixed.log)直接链接完整真实栈；仅RTOS/24MHz/IRQ/IO/DMA完成模拟。
normal实际自然进Operational、运行100ms、105个模拟SoC/374次TX完成、有序排空/退出，live0。
1MiB受限宿主模型加128KiB非PLK预留时峰636816B/余411728B；不是实机FSC峰。
P3i原有10轮周期测试和P3h27+4及更早累计原生回归仍通过，见[第二次全量构建](linux-final-repro.log)。

18场景：normal、heap_full、heap_small、context、no_completion、no_progress、late、dma_fault、tx_error、
wrong_context、nmt_timeout、reset_command、off_command、stop_cycle_failure、stop_failure、timer_release_failure、readback、total_budget。
无完成/无进展/迟到均由**生产probe**触发，不由测试调用m7_plk_fault代替；失败不进入关断或释放。
小堆仍保存0xb3首错，未裁减OD。owner4场景覆盖单槽busy/失败/不完整输入/重入/只读结果及一次性消费；该层mock probe，真实probe另测。

首次[全量编译/链接](linux-first.log)因新fixture漏mock lease符号失败，补fixture后进入执行。
首次运行把PreOp1的3ms正常空闲误算成首帧已等待2ms；[原始失败](linux-native-first.log)、两份debug日志保留。
修复为独立pendingCounter/lastTxCounter后通过；不是放宽2ms门槛。owner首次链接漏integrated.o同样保留并只补测试依赖。
[第二次全量命令](linux-final-repro.log)已完成编译、候选、11产物比较，但最后一个Python测试要求完整历史目录而失败，整体EXIT1如实保留。
仅将原P3i清单覆盖单元测试改为检查选择逻辑，完整清单仍由checkpoint验证器逐项核实；最终Linux215项通过。
[Windows215项](windows.log)也通过。新增7项源码边界不是实际原生或实板回归的替代。

## 两个全新构建与固定候选

Docker `dev_openeuler`，根 `/home/openeuler/build/powerlink-cycle-p3j-20261102`。
`software`/`software-repro`均从固定归档完整编译native+AArch64，无复制旧核心；`UniProton-first`/`UniProton-repro`为两新累计树。
[比较](repro.json)：9个AArch64库/对象加两路runtime逐字节相同；native编译/测试通过但未逐字节比较，ELF调试路径不比较。

最终固定UP2候选：[tl3572-m7-powerlink-p3j-up-b.elf](candidates/tl3572-m7-powerlink-p3j-up-b.elf)。
SHA256 `4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`，1220888B。
UP2 runtime639868B，SHA `2e9520061e436e4c04ee990c41e43b8914546166e89ac81b778bb1dcab47ab8e`。
UP1 runtime360716B/d4d80d02...保持不变；正式M7两ELF仍8bfb824b.../627545f5...，板端M6未访问/替换。

[第一根最终审计](candidate-final-audit.json)、[第二根审计](candidate-repro-audit.json)：

- 598个既有完整核心函数保留，新guard/owner/查询及全部旧诊断存在；未解析符号0、LSE0，125条既有SIMD无新增，不是全ELF无FPU。
- UP2 image/BSS2695664B/8MiB、FSC1MiB、MMU10/16页；UP1 FSC512KiB/MMU9页。
- native与AArch64实际编译布局均 `[608,8,480,496,520,532,544,576,584,1504]`，与真实ELF私有符号对应。
- TTY输入帧336B（旧320B），关键日志链2960B+1024B预留=3984B≤4096B，额外余112B。
  Worker已知帧624B+probe144B，32KiB owner栈有显式8KiB预留；均不是所有库/IRQ最坏栈证明，实板须看真实TCB与峰值。

旧上游/链接告警保留，不称无告警或生产就绪。`candidate-first-audit.json`是最初原样报告，继承的commands字段未列全；
最终审计明确列出实际15条累计命令，未因此改变ELF。

## 换机复现与下一步

恢复[固定源码/SDK/Docker](../../../../repro-inputs/rk3572/README.md)，在stage07运行：

```bash
export TOOLCHAIN_PATH=/path/to/toolchain-14.3
export POWERLINK_BUILD_ROOT=/tmp/p3j-software
bash build/build_m7_powerlink_cycle_probe.sh
UNIPROTON_ROOT=/tmp/UniProton-p3j bash build/build_m7_powerlink_cycle_probe_candidate.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

软件/累计树必须不存在；按固定M6恢复说明设置M6_UNIPROTON_ROOT。脚本只构建/审计，不部署。
新SHA256SUMS包含源码、0021、两个新运行/构建脚本、旧全阶段依赖、失败日志、双根审计、候选与复现证据；旧清单不重生成。
GitHub新检出和服务器后验日志不纳入自身清单，实际同步状态以最终报告为准。
下一步准备新候选的板端预检、608B/FSC/停核交叉证明和独立永久单次窗口，再另确认隔离回环与有限协议帧授权。
不能运行旧P3h runner、复用已消耗许可或直接接真实CN/伺服。CAN/UART“先不要发送”继续有效。
