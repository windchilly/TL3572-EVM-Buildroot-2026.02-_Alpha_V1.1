# UP2 ETH2 直驱增量：V3 PHY / 轮询 DMA / 实机 L2 收发通过

## 2026-10-10 最新结论：V3 实机及复编通过

用户确认调试口一直是 **COM7** 并人工重启板卡。pyserial成功打开COM7，
按项目已实测的UART0参数115200 8N1接收；发送一个回车后出现Linux登录提示。
没有向工控UART发送任何数据，也没有本轮自动重启、刷写、修改持久DT或原M6配置。
开始时SSH曾连接失败，随后Ping/SSH恢复；原始串口接收与现场核验日志保留。
本轮boot_id=`fa41fc54-86a5-46f4-84a0-d2e820e1ef17`，micad PID322/NRestarts0，
kernel taint4096（仅既有out-of-tree模块，没有TAINT_DIE），V2辅助模块残留消失。
ETH3电源服务开机执行成功；这证明该服务此次启动有效，不等于整套UP外设冷启动验收。

成套更新V3模块、两份累计ELF、执行器及共享根检查后，四轮全部成功：

| 原始日志 | 测试 | UP2结果 | 双UP清理 |
|---|---|---|---|
| run-03-probe-v3.log | MDIO/PHY，不发送测试帧 | ID 0x7b744412，MAC 0x5051，100M全双工 | A→B，PASS |
| run-04-frames-v3.log | probe→64B→1514B，各1000次请求/应答 | 序号/角色/载荷/CRC、DMA rc=0 | A→B，PASS |
| run-05-frames-v3-reverse-stop.log | 同一对固件，重复上述收发 | 同上 | B→A，PASS |
| run-06-frames-v3-cpu-load.log | 四个nice19 Linux CPU worker下重复收发 | 同上，负载进程清理PASS | A→B，PASS |

每方向累计 **6000测试帧 / 4734000原始字节**；每种帧长每方向3000帧。
每次重新初始化都由UP2自己写own clock/reset/mux、MDIO配置与PHY软复位/重新协商，
MAC/DMA直接访问自己的寄存器和Normal-NC DDR，无Linux数据/PHY代理。
Linux辅助模块只持有共享NVM0电源和ACLK/PCLK根引用；不启用GMAC叶时钟，不改根rate/parent。
实际共享根ACLK297MHz、PCLK100MHz；解绑后CRU42=0xf000、两共享根均开启。
UP1始终被动，不映射ETH资源；两路CAN/RS232/RS485工作计数全0，原绑定和资源快照不变。
实际页表UP1 9/16页、48项，UP2 10/16页、67项，每轮完整PTE核验。

各轮均有`QUIESCED reset=1`和`CLEANUP PASS`：CPU4/5 PSCI OFF，临时客户端/端点删除，
Linux GMAC1重绑、ETH2/ETH3恢复100M全双工后卸载供电模块。
结束ETH1仍192.168.2.141/24、默认路由不变，micad PID/重启数和boot_id不变，failed units0。
最终Linux eth1/eth2 RX/TX errors为0，但eth2累计TX dropped=28、管理eth0 RX dropped=244；
未取得重启后的起始这些计数，不能宣称整机或接口累计“零丢包”，也不能确定这些丢弃的归因。
目标6000个请求及6000个应答全部逐帧核对；每轮1514B另过滤1个非目标帧，未鉴别其来源。
此前另发现的MCS create/rm fd泄漏未在本轮修复，不能称整个MCS无泄漏。

### 累计交付与复编

仓库`firmware/tl3572-m7-integrated-up-{a,b}.elf`更新为实际测试的V3对，
保留全部原CAN经典/FD/BRS、RS232、RS485、内存日志与RPMsg控制，再增加UP2 ETH。
默认passive，`run all`仍不包含ETH；没有增加各功能专用的默认交付ELF。
旧正式MMU修复版本在父提交e1add984的Git/LFS历史中；历史固定校验清单不回写。
`firmware/m7_eth2_power_hold.ko`为本次匹配板端6.12.69的V3共享资源辅助模块，非网卡驱动代理。

- 实测UP1 ELF SHA256：8bfb824b9f73967add8d27535bc275f9bcbb9dbbdb671ffaf3bf83edf375d14c
- 实测UP2 ELF SHA256：627545f53ffba3d876973371042c70174c254734f433f01afc1b47578057e660
- V3模块SHA256：b071d4346d0d3310e22ffd2d1ae9ce2dcc1f3a2784ae94efd05a0798a546fc8d

两棵全新M6派生树`src/UniProton-m7-eth-direct-{verified-20261010,repro-verified-20261010}`
独立prepare/build、预算/ELF核验、native检查通过。
`build-verified-repro.log`和`compare-tested-v3-repro.log`确认两树及实测V3的objcopy运行镜像逐字节一致：
UP1 `074cdb3a020d463a2203a7163e8b59a1329c4e0dce920f0055b1e65d928f64cf`，
UP2 `a56ed70be2a1f29b51eca1163711d6d6b5ffaab5b6f35a6a75cd45cd95c88579`。
完整ELF含目录调试路径，跨目录ELF哈希不同，不能称完整ELF逐字节一致。
V3模块再次构建哈希一致。复用M6库和匹配内核构建树，非全量Yocto/内核/OS库重建。
原生解析器+18调度/生命周期+3codec及Windows/Linux55项Python检查通过，原始失败日志保留。
随后模块构建器补齐独立可写输出与TL3572_KERNEL_SRC/BUILD参数，
在原手工内核树和2026-09-28干净复现的Yocto内核树各编译成功，vermagic均匹配。
日志power-hold-writable-output-build.log与power-hold-clean-yocto-build.log；
这些换目录模块SHA分别2d4d6611...、4f48f62a...，没有加载到板卡或替换实测ko。
因此仅记录“新构建入口通过”，不宣称这些模块额外通过实机；旧同目录重编的完整SHA一致仍成立。

### 换机复现与受控测试入口

先按[完整换机入口](../../../../../repro-inputs/rk3572/README.md)恢复固定Docker摘要、
LFS完整源码/工具链，执行`run.sh prepare`、`run.sh m6-up`准备M6库；
仓库须保持包含本记录和0010补丁的提交；旧入口的checkout 5655fb0仅用于历史M6核验，
不能在那个旧提交构建当前ETH增量。本目录SHA256SUMS固定本次代码、固件及原始证据。
执行`run.sh m6-image`，其中linux-tl3572配方从源码生成匹配6.12.69内核/Module.symvers。
没有`run.sh kernel`子命令；配方并非virtual/kernel provider。
新机器的Yocto内核源码/构建目录与原机器手工目录不同，必须指定给模块构建器。
容器内，仓库挂载为/repo时：

```sh
export STAGE_ROOT=/repo/stages/stage07-peripheral-partition
export PROJECT_ROOT=/home/openeuler/build/tl3572-2oo3
# m6-image完成后只接受一个已构建的linux-tl3572源码树，不使用linux-dummy。
mapfile -t task_symvers < <(find "$PROJECT_ROOT/build/build-tl3572/tmp/work" \
  -path '*/linux-tl3572/*/linux-6.12.69-v1.0-gf1b67c2/Module.symvers' -print)
test "${#task_symvers[@]}" = 1
export TL3572_KERNEL_SRC="$(dirname "${task_symvers[0]}")"
export TL3572_KERNEL_BUILD="$TL3572_KERNEL_SRC" # 本配方B=S
export REPRO_TAG=eth-verify-new-machine
bash "$STAGE_ROOT/tests/board/eth-direct-20261010/build-and-reproduce.sh"
```

ko输出在`$PROJECT_ROOT/build-m7-eth2-power-hold/`，不在只读/repo源码旁写入kbuild生成物。
新内核的vermagic/Module.symvers必须匹配，不能仅运行modules_prepare代替全量内核符号生成。

准备器拒绝覆盖已存在的目标；链为M6+0001/2/3/7+overlay+0008/9/10，不叠旧0004/5/6。
换目录重建的ELF不能直接通过板端执行器固定整ELF哈希：先比较objcopy运行镜像、
完成静态审计，再明确更新执行器的IMAGE_HASHES；不同内核构建路径的模块也必须审计并更新MODULE_HASH。
不能通过取消哈希检查绕过候选一致性核验。直接使用仓库实测ELF/ko则保持当前固定哈希。

临时目录`/root/m7-eth-direct-20261010`放入两ELF、ko、两份AutoBoot=no配置、
run_eth_direct.py、run_eth_with_cpu_load.py、eth2_resources.py、
eth3_l2_smoke.py、run_can_direct_pair.py、run_integrated_passive.py、
can_resource_preflight.py、rs232_resources.py、rs485_resources.py、
integrated_mmu_resources.py、audit_integrated_mmu.py、verify_integrated_elf.py；
需已有修复版micad、MCS模块及`/usr/libexec/m7/up_log_reader.py`。
板卡UART0可用COM7/115200抓取Linux控制台，UP日志仍在独立内存环，不占UART4/8。
只有确认ETH2↔ETH3隔离连接、ETH1管理路径及全套预检通过，才执行：

```sh
cd /root/m7-eth-direct-20261010
python3 run_eth_direct.py                         # 只读
python3 run_eth_direct.py --confirm-board-loop --profile probe
python3 run_eth_direct.py --confirm-board-loop --profile frames
python3 run_eth_direct.py --confirm-board-loop --profile frames --reverse-stop
python3 run_eth_with_cpu_load.py --confirm-board-loop --profile frames
```

DMA未证明QUIESCED则保留UP2/供电，不CPU_OFF或Linux重绑；不得自动重启代替诊断。
本轮证明**100M轮询DMA L2直驱切片**，不是中断、IP/TCP/工业以太网、吞吐量/实时性、
运行中拔插恢复、单边故障恢复、未知初始硬件状态冷启动或持久DT移交验收。
CAN/UART接线变化后的发送禁令仍有效；新ELF未重测三类工业物理接口/并发，M7.0仍IN PROGRESS。

以下为V2失联及V1故障历史；其中“未部署/未测试”只描述当时，不覆盖上述V3结果。

## 2026-10-10 续测最新状态（优先于下面V1历史记录）

用户对上一轮“是否允许重启一次并继续”回复“继续”，执行一次`systemctl reboot`。
新boot_id=a10d48bb-941b-4e25-9df2-2969e81cfcba；micad PID319 active/NRestarts0；
V1 coming模块消失，kernel taint=4096，不再含TAINT_DIE。
ETH3电源服务Result=success/active(exited)，两测试端100Mbps UP；ETH1地址及路由正常。

已在板端更新并实际加载V2模块（e1eeb617...）；NVM0中的辅助设备active。
Linux GMAC1解绑成功，NVM0仍ON；原累计候选双实例启动：
UP1真实页表9/16页、48映射，UP2 10/16页、67映射，早期MMU记录rc=0且实际PTE全部一致。
这些通过项记录在run-02-probe-v2.log，不能扩大成PHY/MDIO/DMA成功。
执行器进入PHY探测阶段时ETH1 Ping/SSH失联；记录止于UP2 MMU核验，
没有捕获板端[eth]初始化完成/QUIESCED，也没有取得之后的寄存器或异常栈。
本轮没有执行frames分支，64/1514B帧收发仍**未测试**。
SSH传输180秒超时，不代表板端已安全停止或清理；当前UP实例/CPU/GMAC状态无法确认。
用户说“硬接线还在，你再试一下”后再次尝试：Ping仍无回应，SSH出现连接/协议banner失败。
本机Ports/SerialPort和构建服务器ttyUSB/ttyACM均未枚举到USB调试串口。
构建服务器到板卡IP路由落在Docker网桥，不能拿它的ping当作独立物理网络证明。
需要用户明确UART0接在哪台机器/哪个COM(ttyUSB)，获取现场日志；若无法读串口，需人工断电恢复。

### V3防护性修正（编译通过，未上板；不是已证实的根因修复）

本地vendor clk-rk3572.c确认NVM0共享ACLK/PCLK根也有独立门控；
V2仅保持供电并不能保证两共享时钟保持ON，原代码缺少这一前提检查。
这是已证实的软件防护缺口，但没有失联后的CRU快照，不能断言失联一定由此造成。
V3辅助模块在Linux CCF中持有**aclk_nvm0_root/pclk_nvm0_root两个共享根**引用，
不保留GMAC1叶时钟、不设置速率/父源、不读写MAC/PHY/DMA。
UP2仍自行开启/配置独占叶时钟、复位、引脚和直接MDIO/DMA收发。
新增eth2_resources.py在Linux解绑后只读CRU、验证根门控；未通过则不启动UP。
固件在任何GRF/MAC交易之前同样检查共享根，未通过打印SAFE-NO-START并返回9，
不对不可访问MAC做“清理复位”；新增分组日志便于定位clock/mux→GRF→MAC reset→MDIO。

新构建树`/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-eth-direct-guard-v3-20261010`，
旧树/旧候选不改，正式firmware仍未替换。V3本地候选在`.local-only/work/up2-eth-direct-guard-v3-20261010`。

- V3模块SHA256：b071d4346d0d3310e22ffd2d1ae9ce2dcc1f3a2784ae94efd05a0798a546fc8d
- V3 UP1 SHA256：8bfb824b9f73967add8d27535bc275f9bcbb9dbbdb671ffaf3bf83edf375d14c
- V3 UP2 SHA256：627545f53ffba3d876973371042c70174c254734f433f01afc1b47578057e660

V3编译、ELF/页表预算、原生C检查通过；Windows/Linux各55项Python单测最终通过。
build-guard-v3.log尾部Python失败是隔离镜像缺少正式ELF及host测试输入；补齐输入后
linux-python-tests-clock-guard.log仍缺eth3_power_enable.py，最终文件为
linux-python-tests-clock-guard-final.log；所有失败日志保留，不把初版脚本exit1记为整体PASS。
V3/module/helper都**未部署板端、未做硬件验证**；新执行器已固定V3哈希，恢复后必须成套更新，
不能仅复制脚本直接跑仍在板端的V2模块/旧ELF。
此条当时变更未提交/推送；M7.0/ETH2直驱未验收，后续V3切片结果见顶部。

以下为第一次V1故障和当时的恢复计划，保留审计历史，不代表当前板卡状态。

2026-10-10，父提交 e1add984123835576fc0b52028d7531f6eae6b1d。
用户授权测试 ETH2/UP2，ETH2↔板上 ETH3 隔离网线连接；CAN/UART 接线已改变，仍禁止发送。

## 软件范围与已验证项

在原累计固件增加第四个工作任务、`M7 run eth 0/64/1514`，UP1拒绝ETH命令；
`M7 run all`仍只包含CAN/RS232/RS485，不隐含启动ETH。默认被动启动。
UP2增量代码自行初始化GMAC1独占时钟/复位/引脚、MAE0621 Clause22 MDIO及PHY、MAC与DMA。
首切片只设计轮询DMA和实验EtherType0x88b5，不是IP协议栈、中断、带宽或冷启动验收。
64/1514B各1000次请求/应答是**计划**，本轮均未执行。
DMA使用UP2预留DDR内0x7ca10000–0x7ca1ffff，Normal non-cacheable/RW/XN，
不与8MiB镜像或64KiB页表重叠；GMAC仅映射0x2a040000起8KiB，NVM0 GRF单页。
UP1没有新增ETH MMIO/DMA映射。静态检查UP1 9/16页、UP2 10/16页通过。

新鲜M6基线叠加0001/2/3/7/8/9/10及覆盖源，在dev_openeuler：
`/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-eth-direct-20261010`。
复用既有M6库，未重建完整Yocto/内核/UniProton库。原libc/proxy/RWX链接警告保留。
候选ELF仅位于上述构建目录、板端临时目录以及本地`.local-only/work/up2-eth-direct-20261010`，
**没有替换正式firmware目录中的上一版累计ELF，也没有记为实机通过**。

- UP1候选SHA256：e44c3a976f5da58a29fab4db6ce50cf4a028e1716d0511fa17117941ce1d15eb
- UP2候选SHA256：b05e3e63e3794ce61e660c27aa8a209dcc9ee7fd9cbb79c295ab9fde0c4d851d
- 原生C：解析器、18组调度/部分任务创建失败清理、3个codec均通过；ETH CRC标准向量、
  2000序号、错误角色/序号、每个载荷/CRC位翻转检查通过。
- Python既有53项通过；上述均是软件检查，不能替代硬件收发验证。

## 首轮故障与责任

NVM0是Linux管理的共享电源域，直接解绑GMAC可能掉电。
新增GPL辅助模块只准备持有NVM0 runtime-PM引用，不应代理任何MAC/MDIO/PHY/时钟/收发。
V1错误地给虚拟platform device留下`dev.of_node=NULL`；vendor
`rockchip_pd_attach_dev()`无条件调用`of_clk_get(dev->of_node, i++)`，
触发空指针地址0x10，PC=`of_clk_get+0x3c/0xd0`、LR=`rockchip_pd_attach_dev+0x78/0x128`。
这是本轮新增辅助代码引入的错误，不是历史UP页表或PHY硬件问题。
`insmod` SIGSEGV(-11)，模块停留`coming`、引用1；不能强制卸载或在当前内核继续交接。
原始源码/执行器/模块保存在power-hold-v1.c、run_eth_direct_v1.py、power-hold-v1.ko，
完整dmesg为power-hold-v1-oops.log，失败过程为run-01-probe.log。
该日志中的“power hold removed / CLEANUP PASS”只基于insmod未返回成功而误判；
**它不成立**，final-readonly.log确认模块仍残留，已修正新执行器增加显式模块残留与TAINT_DIE拒绝检查。

失败发生于交接开始之前：未解绑ETH2，未创建/启动临时UP实例，未执行ETH命令/发送测试帧。
Linux ETH2/ETH3仍100Mbps链路UP，原UP两实例Offline、CPU4/5 PSCI OFF、RPMsg端点为空，
ETH1 192.168.2.141与路由正常，micad PID320 active/NRestarts0，failed units为空。
本轮进入时boot_id已从上次记录改变为1ac51aef-439d-4234-8948-f9bbe7365585；
本轮前后该ID不变，本轮没有重启。kernel taint=4224包含TAINT_DIE。
CAN/串口Linux绑定及资源快照未改。无法因此称整个内核健康。

## 修正与恢复入口

V2先分配platform device，明确获取现有`/chosen`真实节点且检查其没有clocks属性，
再注册/attach。这样Rockchip的of_clk_get有合法节点，又不会借用MAC节点保持MAC时钟。
platform device release负责of_node_put，已核对vendor platform.c。
V2在匹配板端6.12.69构建树重新编译通过，尚未部署/加载/实机验收。
V2模块SHA256：e1eeb61717c60519e521c6ded719a83050b58642f776a6b649240a150b85cab3。

下一步必须先取得一次新的板卡重启授权，清理OOPS/coming模块及可能残留电源域锁。
不要用rmmod -f，不重试V1，不在污染内核强行解绑GMAC。
重启后重新检查ETH3电源服务、ETH2↔ETH3链路、ETH1管理、CPU4/5 OFF、原两实例Offline、
TAINT_DIE清除与V1模块不存在；更新板端helper/module为V2、核验候选ELF及module SHA后：

```sh
python3 /root/m7-eth-direct-20261010/run_eth_direct.py --confirm-board-loop --profile probe
# 只有probe/安全清理全部通过后：
python3 /root/m7-eth-direct-20261010/run_eth_direct.py --confirm-board-loop --profile frames
```

后续若DMA未确认QUIESCED，执行器保留供电及UP2所有权，不CPU_OFF、不重绑Linux。
本记录不是M7.0/ETH2直驱通过证明。第二树复现、真正物理收发、IRQ、实时性/异常恢复、
持久DT及冷启动仍未完成。当前改动尚未提交/推送GitHub。
