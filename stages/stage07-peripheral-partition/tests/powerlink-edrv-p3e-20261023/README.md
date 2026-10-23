# P3e：UP2 / ETH2 真实EDRV隔离物理收发检查点

2026-10-23，用户确认ETH2↔ETH3板上网线隔离回环仍在，并允许临时UP2接管、有限专用帧和安全停止。
**一次上板成功：64B/1514B各32组请求应答，UP2接收/发送完成/FCS各64，错误为0，安全归还Linux通过。**
不启动POWERLINK MN，不发CAN/串口，不改开机/DT/正式固件，不开COM7、不重启、不自动重试。
本检查点不是MN/CN互操作、持续负载、IRQ收发、实时最坏时延或整个M7.0验收。

## 实板结果与边界

[原始完整日志](board-test.log)、[机器结果](board-result.json)、[实际输入SHA](board-input-sha256.json)。
ETH2=eth1/GMAC1/2a040000.ethernet由CPU5上的UP2真实EDRV控制MAC/DMA/PHY；ETH3=eth2/USB sr9900仅作Linux物理对端。
Linux只保持共享NVM0电源/根时钟，不代理UP2收发。沿用P3d修正的ARMv8-A BSP约束，无LSE指令。

| 检查项 | 结果 |
|---|---|
| PHY/MAC | forced100M half、AN off，MAC启用值0xc003；ETH3独立报告100Mb/s Half/link yes |
| Linux ETH3请求/应答 | tx=64 / rx=64；64B、1514B各32组，完整原始帧逐字节一致 |
| UP2真实EDRV | rx=64、submitted=64、TX完成回调=64、接收FCS匹配=64 |
| 硬件错误 | rxerr=0、txerr=0、DMA fatal=0；背景过滤drop=1，不是丢测试帧 |
| 安全停止 | clean=1；MAC/TX/RX/SWR/MACIRQ/DMAIRQ六回读0，lease=0/0 |
| MN / 工业worker | MN COLD、processes/events=0；CAN/RS232/RS485/旧ETH worker done均0 |
| 最终资源 | CPU4/5 PSCI OFF，原up-a/up-b Offline；临时client/端点/hold已清理 |
| Linux恢复 | ETH2/ETH3均100M full/AN on；CAN/UART寄存器与绑定、管理口地址路由不变 |

[前只读快照](board-preflight.log)与[最后只读快照](board-final.log)：
boot_id `6974ac40-f3a2-4433-a5b8-11ec4318248f`、micad PID328/NRestarts0/active始终不变；
ETH1/eth0仍192.168.2.141/24，CPU集合0-3,6-7，CAN四口DOWN，无新增Oops或失败服务。

接收FCS不是只算载荷CRC：回调核对真实NC DMA RX槽地址/长度，再读取帧后保留的4字节Ethernet FCS，与整帧CRC32匹配。
Linux核对应答不含FCS的完整64/1514字节。没有物理坏FCS注入，也没有独立抓取TX线上FCS；不能称这两项通过。
有限低速串行请求应答不等于吞吐/长期可靠性，未重测P3c timer IRQ/迟到。

专用EtherType0x88b5、magic M7EDRV01、role/sequence/pattern/appCRC，以及计数器派生每轮标记隔离旧帧。
AF_PACKET的本机PACKET_OUTGOING不能计为应答。nonce READY为0xce3f922b；缓存printf显示0xffffffffce3f922b是既有PRT格式化高位符号扩展，
真实wire nonce固定低32位，非密码学随机。普通Linux背景流量未宣称为零。

## 增量源码与软件验证

`source/powerlink/port/m7_edrv_probe.c/h/codec.h`执行**真实现有EDRV和target**，不改EDRV/BSP核心实现。
static TX元数据在不安全停止时持续存活，单pending缓冲容许前一TX完成前到达下一请求；不在RX回调发送。
固定32+32组、20秒/40000循环双界限。只进行一次停止尝试；不能证明停DMA/清lease时保留owner/hold并拒绝重试。
`rk3572_powerlink_app.c/h`增加COLD显式`PLK edrv-probe`和缓存`PLK edrv-status`，默认休眠不运行。
0017默认OFF、CPU5-only，保留timer/PHY和全部累计CAN/FD/串口功能；不调用oplk_initialize/create/NMT或租用高精度timer。

[容器原生/122项Python最终日志](native-final.log)、[Windows日志](windows-tests.log)。新增：

- 真实probe+EDRV+target的17场景：正常10轮、无对端/时钟冻结、坏FCS/载荷/nonce/重复/截断、TX error、DMA fatal、模式错误、
  安全/不安全acquire/start/stop失败及上下文拒绝；mock边界不冒充物理坏帧测试。
- 真实累计owner/邮箱3场景：100轮EDRV/timer/PHY命令、busy/COLD限制、不安全终止、非法输入。
- 编译后的C codec与独立Python/zlib逐字节比对64B/1514B向量；7项新增Python检查。
- 既有P3d/P3c/P3b、P0/P1/P2/P3a和累计parser/18生命周期/3codec回归继续通过。

没有ASan/UBSan；原M6 endian/RWX告警保留。[首次原生](native-first.log)、[首次候选构建](candidate-first.log)、
[第二根构建](candidate-repro.log)均成功，原始日志不裁剪。
旧CTest元数据执行原固定二进制；9份旧软件对象从已验证P3d根复制，不冒充本轮新编核心。

## 构建位置、候选及复现

Docker `dev_openeuler`：`/home/openeuler/build/powerlink-edrv-p3e-20261023`。
`software`/`software-repro`是明确复用的旧软件根；`UniProton-first`/`UniProton-repro`是两份全新累计源码树，均真实编译。
[双根比对](repro-comparison.json)9旧产物哈希相同、2份新runtime逐字节相同；ELF的绝对DWARF路径不纳入逐字节承诺。
[第一根ELF审计](edrv-probe-audit.json)、[第二根审计](edrv-probe-audit-repro.json)。

实测[UP2候选ELF](candidates/tl3572-m7-powerlink-p3e-up-b.elf)另存LFS，1,169,496 B，SHA256：
`03af506dad24fe31060aed037fa5b6c7246d7d4e5c0a6cf189fc079e888973d1`。
UP2 runtime621356B，SHA `9b41c399a687d2c29c40cdc0f016e581363acdbb0ea602d15735fe54e838b79a`；
image/BSS2148768B/8MiB，FSC512KiB、页表10/16。UP1 runtime仍360716B/d4d80d02...，页表9/16，本轮未上板。
596旧全局函数保留、最终未解析零、LSE零、无新增FP/SIMD；125条旧M6/libmetal指令仍在，不是整个ELF无FPU。
这些是静态预算，不是运行时堆/栈峰值。正式两ELF仍8bfb824b.../627545f5...，不替换M6内核/rootfs。

换机先恢复[完整M6源码/SDK/内核/工具链及固定摘要Docker](../../../../repro-inputs/rk3572/README.md)，然后：

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3e-new-machine
# 两个输出根须不存在。换机从完整源码构建软件根，不依赖本轮复制目录。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
  bash "$stage/build/build_m7_powerlink_edrv_probe_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_edrv_probe_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

第二组新根完成后：`compare_powerlink_p3e.py software1 software2 Uni1 Uni2 report.json`。
板端重复测试需重新确认隔离接线和有限帧授权、原两UP Offline及独立PSCI OFF。
上传`board-input-sha256.json`列出的helpers/config/实际候选到`/root/m7-powerlink-edrv-p3e-20261023`；
候选文件名/路径须与`up-b-m7-plk-edrv.conf`一致。日志reader `/usr/libexec/m7/up_log_reader.py`由已归档M7软件安装。
沿用匹配内核6.12.69-gf1b67c293213的`firmware/m7_eth2_power_hold.ko` SHA b071d434...，
放`/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko`；源码/Makefile/build脚本均已归档，本轮未重编该模块。
执行`python3 run_powerlink_edrv_probe.py --confirm-isolated-loop-frames --sha256 实际候选SHA`，固定64组，不接受无限次数。
未知停止保留资源，不自动强停/重绑/移除hold/重启；不能套用P3d旧CASAL故障的专用恢复脚本。

服务器`delivery/`按本目录SHA256SUMS保存完整输入/源码/脚本/候选/证据，根README为入口；
历史清单须到历史commit核对。GitHub后验日志不列入自身清单，最终上传状态以最终报告为准。
首次GitHub精确稀疏检出403项SHA均匹配，但发现旧清单漏列已在仓库的`build/prepare_m7_powerlink.py`，导致测试导入失败；
[首次记录](github-verification-first.log)保留。当前清单显式补齐准备脚本，后验完整重测记录见`github-verification.log`。
板端保留临时输入/结果但无AutoBoot注册。下一步可准备受控MN reset/停止及隔离CN互操作，须单独授权，不能直接控制真实伺服。
