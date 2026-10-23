# P3f：完整MN栈GsOff生命周期软件检查点

2026-10-23，延续P3e累计固件，新增同一UP2 owner的完整栈生命周期诊断。
**软件准备完成，未访问、部署或操作板卡；不是MN reset/start或CN互操作通过。**
上轮有限EDRV测试帧许可不自动扩展为本轮ETH2/CNTP联合移交或MN运行许可。

## 增量范围与真实调用

`m7_mn_probe.c/h`、0018、`build_m7_powerlink_mn_probe_candidate.sh`，默认OFF/CPU5-only。
COLD显式`PLK mn-probe`执行真实：initialize → prepare → 128次process → stop → exit；`PLK mn-status`仅读缓存。
保留所有已有timer/PHY/EDRV诊断与CAN/FD/RS232/RS485功能，启动仍休眠，不自动运行诊断。
调用的是已完整链接的真实API/OD/CFM/PDO/target/hrestimer/EDRV，不用假的oplk成功桩。

prepare **会获取ETH2 PHY/MAC/DMA和CNTP/PPI30**，不是只读；但不调用NMT reset/start/switch-off，实际NMT始终GsOff。
每次处理检查状态/事件、TX完成和全部TX描述符四个word；“完成0”不能单独证明“未提交”，因此也必须描述符从未使用。
检查timer回调/IRQ为0。过程有128次迭代与2秒软件guard，但不能抢占卡死的API或保证RTOS最坏调度时间。
停止后证明MAC/TX/RX/SWR/MACIRQ/DMAIRQ关闭、lease0、timer未租用、CNTP/PPI30静默、CNTV/PPI27/priority未变，再退出环境。
部分初始化/处理/停止/回读失败都是终止状态，保留资源/owner、worker拒绝重试，不自动第二次stop/exit。

## 已完成的软件验证

[真实原生首次日志](native-first.log)、[最终原生/Python回归](native-final.log)、[Windows测试](windows-tests.log)。

- 真实完整栈100轮：12,800次处理，1,600次分配全部释放、live=0；始终GsOff，无TX doorbell/定时器arm。
- 29个原生场景：正常、上下文、PHY/timer/sem失败、16个分配位置失败、ETH/timer停止失败、sleep/DMA/模式/回读/TX描述符/超时故障。
- 3个真实累计owner/邮箱场景（仅probe边界mock）：100轮新旧诊断400命令、busy/COLD限制、不安全终止、非法输入。
- Windows/Linux各129项Python；P3e/P3d/P3c/P3b/P0-P3a和累计parser/18生命周期/3codec回归通过。

这些硬件边界是mock，不当作实板联合生命周期或实时性证据。未开启ASan/UBSan，原M6 endian/RWX告警保留。
旧CTest元数据执行原固定二进制，旧核心未重新编译；新增probe/owner/真实栈调用测试是本轮新编。

## 构建位置与产物

Docker `dev_openeuler`：`/home/openeuler/build/powerlink-mn-p3f-20261023`。
`software`/`software-repro`明确复制已验证P3e软件根，9份旧库/对象不是本轮新编核心。
`UniProton-first`/`UniProton-repro`两全新累计源码树均真实编译；[双根比对](repro-comparison.json)新runtime逐字节相同。
[首次完整构建](candidate-first.log)、[第二根构建](candidate-repro.log)、[第一/第二根审计](mn-probe-audit.json) / [repro](mn-probe-audit-repro.json)。

新[UP2候选](candidates/tl3572-m7-powerlink-p3f-up-b.elf)1,178,136B，LFS保存，SHA256：
`b00cdf67837d3359488385f4709fa1a162cd4ea6a791855c6f9708c1411992c1`。
UP2runtime621924B/SHA `9cca16c01c63795b8ee069bf0f844b478945f039f8dc6b22e304f4229c3a6229`；
image/BSS2149824B/8MiB、FSC512KiB、页表10/16；UP1runtime仍360716B/d4d80d02...、页表9/16。
596旧全局函数保留、最终未解析零、LSE零、无新增FP/SIMD；旧125条M6/libmetal FP/SIMD仍在，不是全ELF无FPU。
静态预算不是实机栈/堆峰值承诺。仅runtime逐字节一致，不承诺不同绝对DWARF路径的ELF完整字节一致。
正式两份累计ELF仍8bfb824b.../627545f5...，M6内核/rootfs/DT/开机配置不变。

## 换机复建与后续板端窗口

先恢复[完整M6输入/工具链/固定摘要Docker](../../../../repro-inputs/rk3572/README.md)。

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3f-new-machine
# 输出根须不存在；换机从完整源码重编软件根，不依赖本轮复制目录。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
  bash "$stage/build/build_m7_powerlink_mn_probe_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_mn_probe_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

第二组新根完成后运行`compare_powerlink_p3f.py software1 software2 Uni1 Uni2 report.json`。
本轮源码、脚本、候选、证据按SHA256SUMS归档到服务器`delivery/`；历史清单到历史commit核对。
GitHub后验日志不列入自身清单，最终上传状态以最终报告为准。

板端runner/config/checker已准备但**未部署/执行**：`run_powerlink_mn_probe.py`固定一次128次处理，无网络socket/发帧命令。
先单独取得隔离ETH2↔ETH3、临时ETH2/CNTP联合GsOff生命周期检查许可，确认两UP Offline/PSCI OFF/无其他owner。
将候选与conf指定路径一致放入`/root/m7-powerlink-mn-p3f-20261023`，上传board Python helpers及
`audit_integrated_mmu.py`/`verify_integrated_elf.py`；reader `/usr/libexec/m7/up_log_reader.py`由已有M7安装。
共用固定模块`firmware/m7_eth2_power_hold.ko` SHA b071d434...，匹配内核6.12.69-gf1b67c293213，
放`/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko`，源码/Makefile/build脚本均已归档；本轮不重编模块。
获准后才执行`python3 run_powerlink_mn_probe.py --confirm-isolated-gsoff-lifecycle --sha256 实际候选SHA`。
未知状态保留UP2/hold，不强停/重绑/自动重启；本脚本不是NMT reset/start入口，更不是控制真实CN/伺服的许可。
通过这一联合生命周期硬件门槛后，再开放受控NMT reset/停止与隔离CN的PDO/SDO互操作。
