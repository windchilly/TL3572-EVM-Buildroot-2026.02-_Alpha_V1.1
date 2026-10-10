# P3d：ETH2 强制100M半双工、无DMA/帧诊断软件准备

2026-10-10：**软件准备、完整候选链接和双新树复编通过；尚未部署或实测半双工**。
本轮板卡仅SSH只读预检，两UP仍Offline；未解绑ETH2、改变PHY、加载候选、开COM7或重启。
正式M6/DT/开机配置及两份累计ELF不变。CAN/RS-232/RS-485“先不要发送”继续有效。
实机窗口须另确认ETH2↔ETH3隔离回环和临时ETH2独占移交，不能沿用P3c的timer-only授权。

## 增量实现和安全边界

- 在同一累计UP2候选、同一owner/单槽邮箱加入`PLK eth-probe`/`PLK eth-status`；保留P3c timer诊断。
  新0015/default OFF/CPU5-only开关，boot不自动执行，命令仅MN COLD可接受，UP1不链接诊断。
- `m7_eth_probe.c/h`调用真实GMAC1/MDIO/PHY BSP acquire，设置并回读100M半双工、PHY AN off。
  PHY必须为0x7b74/0x4412，BMCR=0x2000（控制位掩码），BMSR支持100-half且link=1；BMSR双读。
  MAC设置PS/FES、清DM，但RE/TE保持0；不初始化描述符、不启动DMA、不调用EDRV、MN或timer。
  因此不是物理收发/FCS/POWERLINK协议验收，也不代表节点可运行。
- 先检查上下文/已有软件owner/fault/ETH lease；busy不操作其它owner的资源。
  acquire安全拒绝与不安全部分租用区分，不安全返回不再次stop。
  成功获取后只尝试一次stop，缓存MAC/DMA/IRQ停止回读；stop失败保留lease和主机电源/根时钟保持。
  owner收到clean=0即终止接受命令，不自动重试、强行CPU_OFF、Linux重绑或重启。
- 增强共用EDRV停止证据：SWR清零后再次验证MAC RE/TE、TX/RX start、两路interrupt enable全0，
  再释放lease。原legacy测试行为未改；正式ELF没有被替换。
  `PLK status`的`mode=software-only`描述MN生命周期范围，新增硬件诊断通过独立显式命令开放。

## 软件证据

[原生/容器Python](native-first.log)：8组真实probe控制流+BSP/RTOS mock场景，
涵盖100次重复、ISR/IRQ/context拒绝、已有lease、安全/不安全acquire、mode失败、stop失败和13种错误回读。
3组真实累计owner/mailbox场景覆盖timer与ETH交替100轮、busy/COLD限制、不安全锁定及命令截断/NUL拒绝。
这不是模拟PHY成功来证明硬件通过；只有控制流和边界的软件结果。
P3c 12+3、P3b 12+UP1拒绝回归；Windows/Linux各104项Python通过，另累计parser/18生命周期/3codec通过。
最新默认OFF回归补拒绝ETH两命令，见[native-final.log](native-final.log)。

[首份构建](candidate-first.log)、[另一全新树](candidate-repro.log)、
[最终比对及既有P0/P1/P2/P3a原生重执行](final-repro-fixed.log)、[机器比对](repro-report.json)。
9个旧软件库/对象明确复制复用已验证P3c/P3b/P3a软件根，并非本轮重编72核心；
两累计源树从固定M6独立准备并真实重新编译，UP1/UP2 runtime分别逐字节相同。
复制的CMake原生测试元数据仍指向原已验证软件根，CTest重执行这些固定二进制，不声称它们是新编译。
[早期final-repro.log](final-repro.log)的exit127是追加旧回归误写二进制路径，
在其前面的比对和ELF审计已通过；改为正确CTest目录重执行后全部通过，失败日志保留。
旧endian/RPC/RWX等告警保留，没有sanitizer。

[最终ELF审计](eth-probe-audit.json)：596个原核心/OD/port/BSP全局函数加7个累计诊断函数保留，
最终未解析为零；UP1不含这些诊断。原M6/libmetal125条FP/SIMD逐点比较无新增，整个ELF不是无FPU。
UP1 runtime360716B（与P3b/P3c一致），image/BSS969056B，页表9/16。
UP2 runtime620564B，SHA`802a76ac943384b78ea6a24cdcea86390102abd07b7fc99afd945816b3e7373b`；
image/BSS2146128B/8MiB，FSC512KiB，页表10/16。这是静态预算，不是板端栈峰值/性能验收。
[UP2候选ELF](candidates/tl3572-m7-powerlink-p3d-up-b.elf)为LFS单独归档，
SHA`73689e61b9edbd6f337b6affb47faf057db96ec03d7ba195efad8e3832d6f348`，未安装。
正式两ELF仍`8bfb824b...`/`627545f5...`。

## 板卡现状与保存位置

[仅只读预检](board-preflight.log)：boot_id fa41fc54-86a5-46f4-84a0-d2e820e1ef17，
micad PID322/NRestarts0，CPU4/5客户端Offline，Linux CPU0-3,6-7；无RPMsg端点/残留power hold/Oops taint。
ETH1管理eth0/192.168.2.141保持；Linux ETH2=eth1、ETH3=eth2，两者仍100M full/AN on/link yes。
这不能代替UP2的forced100-half回读、对端双工检查和安全归还。

Docker dev_openeuler：`/home/openeuler/build/powerlink-eth-p3d-20261010`：
`UniProton-first`/`UniProton-repro`两新累计树；`software`/`software-repro`明确复用固定软件。
`stage`保存实际构建输入，`delivery`按本检查点`SHA256SUMS`保存完整源码/脚本/候选/证据，
根README提供入口；没有新板端目录或开机注册。
历史阶段SHA清单到对应历史commit核对；新清单标识当前累计输入，不改历史记录。
GitHub下载后验日志不列入SHA清单，避免自引用；同步/验证结果以最终报告为准。

## 换机完整复建

先按[固定M6完整源码/SDK/工具链恢复](../../../../repro-inputs/rk3572/README.md)，联网下载固定摘要Docker。
新增源码/补丁/脚本/完整日志均提交，不复制重复大源码包或Docker层。

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3d-new-machine
# 两根必须不存在；换机从完整固定源码编译，不依赖本机复用软件目录。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
  bash "$stage/build/build_m7_powerlink_eth_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_eth_native.sh"
bash "$stage/tests/run_integrated_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

第二组新根编译后：`compare_powerlink_p3d.py software1 software2 Uni1 Uni2 report.json`。
下一步获准后准备无帧板端runner：只临时UP2、保护共享电源根、ETH1管理不动、
Linux ETH2移交→显式eth-probe→对端半双工核查→证明停止→CPU OFF→Linux重绑恢复全双工。
任何未知/不安全阶段保留资源并请求恢复方向，不自动重启。通过后才另安排EDRV物理收发，再MN reset/隔离CN。
