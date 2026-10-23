# P3d：UP2 / ETH2 强制100M半双工与安全归还实测

2026-10-23：获准临时独占ETH2，**修正版三轮PHY/MAC100-half与安全停止通过**。
不是DMA/EDRV物理收发、FCS、POWERLINK MN/CN或整个M7验收。
无测试帧、不启动MN/高精度timer诊断、不改开机配置/DT/正式ELF、不打开COM7、不重启整板。
UP1始终Offline；CAN/RS-232/RS-485“先不要发送”继续有效。

## 实测结果

[修正版完整日志](board-test-fixed.log)、[机器结果](board-result.json)、[交叉汇总](hardware-summary.json)。
3轮均rc=0/clean=1，UP2自己配置并回读：PHY ID=0x7b74/0x4412，BMCR=0x2000（100M、half、AN off），
BMSR=0x794d（100-half能力/link）；MAC=0xc000（100M、half、RE/TE=0）。
TX/RX DMA start=0、SWR=0、MAC/DMA IRQ enable=0；不初始化描述符，不调用EDRV start/send。
每轮停止后的MAC/TX/RX/DMA/IRQ六项回读全0，lease从0回到0。
Linux ETH3只作观察对端：3轮都报告100Mb/s/Half/link yes；自身AN仍on，对端声明AN no/100-half。
没有改变ETH3配置，没有用Linux/RPMsg代UP2驱动PHY。

最终停止/删除临时UP2，PSCI确认CPU4/5 OFF；Linux ETH2/ETH3恢复100M full/AN on，shared hold卸载。
[最后只读预检](board-final.log)与[退役DRAM快照](board-dram-final.json)：seq=done=3、running=0、MN COLD，
processes/events=0、lease=0；修正版异常记录为零。缓存读取不代替独立CPU OFF与硬件停止回读。
ETH1=eth0/192.168.2.141管理地址/路由、CAN/UART寄存器/绑定、Linux CPU集合保持。
micad PID328/NRestarts0、boot_id `6974ac40-f3a2-4433-a5b8-11ec4318248f` 全程不变。
`test_frames=0`表示runner/UP2不发测试帧，不表示抓包证明Linux后台流量也为零。

## 首次故障、证据与修复

[首次日志](board-test.log)在BEGIN后RPMsg超时；runner按未知状态保留UP2/shared hold，未强停或重绑。
[只读DRAM](board-dram-snapshot.json)保存异常ELR=0x7c20fe68、ESR=0x02000000/EC0，
[反汇编](candidate-disassembly.log)定位到`TakeLease`内`CASAL w0,w4,[x3]`，机器码0x88e0fc64。
该指令发生在调用`OwnResources`/访问PHY/MAC之前，g_ethLease仍0，完整MN尚未初始化。
旧UniProton模板全局`-march=armv8.2-a+nofp+nosimd`导致这份真实BSP发出目标UP核不支持的LSE指令；
移植核心使用cortex-a53选项并不自动约束另行编译的BSP，`-mno-outline-atomics`单独也不能禁止直接LSE。
此前正式ETH切片没有启用这个EDRV lease路径，所以旧功能通过不能覆盖新路径。
不是PHY半双工不支持、页表容量不足或micad SIGABRT；真实MMU仍10/16页通过。

[CPU事实](cpu-facts.log)随后独立PSCI确认CPU4/5已经OFF，UP2异常处理已自行下线，
但MICA管理表仍写Running。不是我们强行停核，也没有重启整板。
[精确恢复](restore-pre-mmio-fault.log)只有在固定旧ELF/ELR/opcode/零lease/CPU OFF都确认后，
才清理客户端、重绑Linux ETH2、证明两端full并移除hold。
`restore_powerlink_eth_pre_mmio_fault.py`仅用于这次固定故障，不是通用“忽略unsafe”恢复工具。

新增0016，在全部公共source属性之后为ETH BSP追加`-march=armv8-a;-mgeneral-regs-only;-mno-outline-atomics`。
最终ELF审计新增全UP2 LSE扫描及真实compile_commands最后march检查；
[修正反汇编](native-final.log)已为LDAXR/STLXR，不再是CASAL。
原旧P1–P3c/P3d初版候选不要拿来执行EDRV新路径；最新累计入口包含0016。
另外修正runner管理地址比较：不把DHCP剩余租期倒计时误判为资源改变。

## 软件回归与构建归档

新增9组板端解析/保护/快照/租期检查，另2组LSE/编译选项检查；Windows/Linux各115项Python通过。
[本机检查](windows-tests.log)、[容器检查与原生回归](native-fixed.log)、[既有原生重执行](native-final.log)。
P3d 8probe+3mailbox、P3c 12+3、P3b 12+UP1拒绝，累计parser/18生命周期/3codec及旧P0/P1/P2/P3a通过。
硬件边界mock不当作PHY实测；复制的CTest元数据仍执行原固定二进制，明确不是重编旧核心。
早期[构建日志](candidate-fixed.log)是0016上下文不足，改成尾部上下文并在公共属性之后追加；
[v2日志](candidate-fixed-v2.log)构建/ELF审计/原生通过，末尾因transport漏传host Python而有2个导入错误。
补齐上传后[native-fixed.log](native-fixed.log)全部通过，所有失败日志保留。原endian/RWX告警、无sanitizer限制保留。

Docker `dev_openeuler`：`/home/openeuler/build/powerlink-eth-p3d-hw-20261023`。
`UniProton-fixed-v2`/`UniProton-repro-v2`两全新累计源码树真实重新编译，
`software`/`software-repro`明确复制已验证旧P3d/P3b/P3a软件根，9旧产物不是本轮新编核心。
[双根比对](repro-report.json)两runtime逐字节一致；UP1runtime仍360716B，页表9/16。
UP2runtime620564B，SHA `92862487a9378c28856c79e566cf289e452379802ba154041227c5a37ef68065`，
image/BSS2146128B/8MiB、FSC512KiB、页表10/16，仅静态预算。
[最终ELF审计](eth-probe-audit-fixed.json)：596旧全局函数+7累计诊断保留、未解析为零、LSE零。
旧M6/libmetal125条FP/SIMD逐点比较无新增；整个ELF不是无FPU，未重测P3c时延/长稳。
[实际实测候选](candidates/tl3572-m7-powerlink-p3d-armv8a-up-b.elf)另存LFS，
SHA `69720472a318b7d086926d13d105470250676ac98d442eaed18701012319bef7`。
正式两ELF仍`8bfb824b...`/`627545f5...`，不替换M6或旧稳定固件。

板端`/root/m7-powerlink-eth-p3d-20261023`只保留临时输入/结果/首份失败ELF备份，无AutoBoot注册。
原始首份Python输入另存[inputs-first](inputs-first)，其中旧runner不要用于新复测。
构建服务器`delivery`按本轮SHA256SUMS归档源码/脚本/模块输入/候选/完整证据，根README为入口。
历史SHA清单到历史commit核对；GitHub后验日志不列入本清单，避免自引用，最终同步状态以报告为准。

## 换机复建与重复测试

先恢复[固定M6完整源码/SDK/内核/工具链和摘要Docker](../../../../repro-inputs/rk3572/README.md)。

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3d-hw-new-machine
# 两根必须不存在；换机从完整源码构建软件根，不依赖本轮复用目录。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
  bash "$stage/build/build_m7_powerlink_eth_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_eth_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

第二组全新根构建后运行`compare_powerlink_p3d.py software1 software2 Uni1 Uni2 report.json`。
板端只在隔离回环/临时移交获准、两UP Offline且PSCI OFF时，上传当前runner/helpers、conf及实际候选；
固定模块`firmware/m7_eth2_power_hold.ko` SHA b071d434...、匹配内核6.12.69-gf1b67c293213，
放在runner中明确的模块路径；其源码/Makefile/build_m7_eth2_power_hold.sh均在仓库，本轮复用而未重编模块。
按conf路径放候选，执行`python3 run_powerlink_eth_probe.py --confirm-isolated-loop-handoff --sha256 实际候选SHA --cycles 3`。
未知状态保留资源，不自动重试/强停/重绑/重启；不要自动执行首份故障的精确恢复脚本。
下一步应另获准后做EDRV隔离物理帧/FCS/持续收发与停止，再做MN reset/隔离CN；本轮不扩大到发送。
