# P3c：UP2 CNTP / PPI30 定时器诊断检查点

2026-10-10：软件验证和获准的临时 UP2 定时器实测通过，**不是 POWERLINK 主站运行/实时验收**。
正式两 ELF、M6、DT、开机配置不变；未重启，UP1始终 Offline；没有 PHY/ETH/CAN/串口物理发送。
最终临时客户端已删除，CPU4/5 PSCI OFF，原两客户端 Offline，micad PID322/NRestarts0、Linux绑定/地址/路由/boot_id不变。

## 增量实现

- `m7_timer_probe.c/h`调用真实 target/hrestimer，不调用oplk_initialize/create、EDRV或MN启动。
  同一休眠owner新增显式`PLK timer-probe`/`PLK timer-status`，仅COLD可执行；默认不开启、不自动运行。
- 每轮8次100us、8次1ms、8次10ms单次定时，约89ms。每次先观察真实ISR计数变化再process回调，
  不把计数器轮询模拟到期当作IRQ通过。每次20ms超时及千万次迭代上限；停止失败保留lease/FAULT，不重试。
- BSP诊断开关只增加ISR时间戳/计数，ISR不打印、发RPMsg或调用栈回调；回调仍在owner任务。
  IRQ迟到是CNTP目标时刻到C ISR内采样，任务迟到是目标时刻到hrestimer回调处理，不是硬件引脚测量。
- 新0014默认OFF、仅CPU5且依赖MN/RTOS。UP1只保留P3b的PLK拒绝路由，不链接定时器诊断。
  全部596个原核心/OD/port/BSP全局函数和3个新诊断函数保留；最终未解析为零。

## 首次失败及修复

[首次实测](board-test-first.log)返回`rc=2 clean=1`，0 IRQ/0回调，已安全停止；不是硬件IRQ通过。
[只读退役快照](board-snapshot-first.json)显示EL1、24MHz计数器可访问，PPI30未使能/挂起/活动，IGROUPR0=0。
旧P2代码硬要求IGROUPR0 bit30=1，误判非安全视图。
[Arm IHI0048B §4.3.4](https://documentation-service.arm.com/static/5f8ff21df86e16515cdbfafe)规定：
启用Security Extensions时，IGROUPR对Non-secure访问为RAZ/WI，读零不能证明Group0。

新增纯整数`m7_plk_gic.h`按SecurityExtn与CPU接口使能视图判断；依旧拒绝已使能/挂起/活动、边沿触发，
并要求own PPI30使能和优先级回读。没有写安全分组、全局GIC初始化或其它PPI。
失败回滚若不能证明PPI静默，返回faulted lease供hrestimer保留，不虚报未占用。
最终[完整快照](board-snapshot-final.json)实际GICD_TYPER=64749（SecurityExtn=1）、GICC_CTLR=1、IGROUPR0=0，
修正后PPI30真实中断投递成功。MPIDR=0x80000101；检查只比较affinity低24位，不误拒绝bit31。
首次日志还包含之前共享日志环中的ETH历史记录；最终runner使用本轮起始序号，避免混淆。

## 实测结果与限制

[最终原始日志](board-test-final.log)、[机器结果](board-result.json)、[计数换算](hardware-summary.json)。
3轮共72 IRQ、72任务回调；每轮24/24，无丢失/重复。CNTP_CTL=2、PPI30使能/挂起/活动均0；
own priority恢复160，CNTV_CTL=1、PPI27使能/priority保持，系统Tick每轮推进88。

| 轮次 | 最大ISR迟到 / us | 最大任务回调迟到 / us |
|---|---:|---:|
| 1 | 9.875 | 72.292 |
| 2 | 1.417 | 2.750 |
| 3 | 29.292 | 89.750 |

这是空闲板卡且存在RPMsg状态查询/日志活动的短样本，不是最坏时延上限，也没有逐周期漂移/长稳/外设并发验收。
不能据此保证100us周期、节点容量或伺服性能；MN仍COLD、processes/events为0，半双工和CN互操作未测。
CAN/UART“先不要发送”仍有效；没有打开COM7，启动/诊断通过共享内存日志与RPMsg读取。

## 软件验证与保存位置

新增12组真实target/timer/probe原生场景（含GIC安全视图、无IRQ、重复IRQ、冻结计数、部分租用/停止失败），
另3组owner命令场景、100次重复诊断投递。原P3b12组+UP1拒绝、累计原生回归通过；Windows/Linux各99项Python通过。
[既有P0/P1/P2/P3a原生测试重新执行](old-native-regression.log)，其测试二进制复用固定P3b软件根，不声称本轮重编全部核心。
[最终构建](candidate-final.log)保留原endian/RWX等告警；[早期native失败](native-first.log)为嵌套main宏冲突，已修复。
未使用sanitizer；旧M6/libmetal125条FP/SIMD保持逐点比较，无新增，整个ELF仍不是无FPU。

Docker `dev_openeuler`根`/home/openeuler/build/powerlink-timer-p3c-20261010`：
`UniProton-final`/`UniProton-final-repro`为两全新累计源码树；`software`/`software-repro`明确复用固定P3b/P3a软件。
[最终双根比对](final-repro-report.json)两runtime逐字节一致，9个原软件库/对象匹配；ELF调试路径不要求相同。
UP1runtime360716B（与P3b相同）；UP2runtime619876B，SHA`11f1c0e875c37719b70de14a97150ffee1d82777462e5c0c195983385a6d52c6`。
UP2含NOLOAD/BSS=2145344B/8MiB，FSC512KiB，页表10/16；UP1页表9/16，非实机栈峰值验收。
最终[UP2诊断ELF](candidates/tl3572-m7-powerlink-p3c-final-up-b.elf) SHA`a50255ed798c679fd78b7555ff3853698a3a8937934ee4310130473add671b2e`。
`candidates/`也保留首次失败及中间软件候选，不能将其自动安装为正式固件。
板端仅`/root/m7-powerlink-timer-p3c-20261010`临时输入/结果保留，无AutoBoot注册。
`delivery`按SHA256SUMS完整归档；GitHub后验日志不列入该清单，避免自引用，源码/构建/实测输入均列入。

## 换机复建

先按[固定M6完整源码/SDK/工具链恢复](../../../../repro-inputs/rk3572/README.md)，联网下载固定摘要Docker。
本轮没有复制重复的大源码包或Docker层；所有新增源码/补丁/命令/测试均提交。

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3c-new-machine
# 以下两根必须不存在，拒绝覆盖；换机需要从源码构建软件根。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
  bash "$stage/build/build_m7_powerlink_timer_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_timer_native.sh"
bash "$stage/tests/run_integrated_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

再次用全新两根编译，运行`compare_powerlink_p3c.py software1 software2 Uni1 Uni2 report.json`。
板端runner/临时conf放同目录；只在用户批准且两UP Offline/CPU OFF时手动执行：
`python3 run_powerlink_timer.py --confirm-timer-only --sha256 实际ELF哈希 --cycles 3`。
runner不上传、不自动启动其它外设；不安全状态保留UP2，不强行CPU_OFF、重启或重试。

下一步：forced100-half PHY/MAC/安全停止的受控硬件窗口，再做延迟长稳/负载预算；满足门槛才开放MN reset/start和隔离CN。
