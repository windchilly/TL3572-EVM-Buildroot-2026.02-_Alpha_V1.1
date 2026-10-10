# POWERLINK MN P3a：真实完整栈的被动软件接入

日期：2026-10-10。UP2做MN，通过ETH2直驱；继续累计两份固件路线。
本次是P3第一部分：**portable单owner生命周期、真实OD/内存CDC与完整栈强制链接**。
尚未增加UniProton常驻owner task、RPMsg命令或P3累计候选ELF，不是整个P3完成。
未连接板卡/COM7，未执行真实GMAC/PHY/CNTP、发帧、解绑、部署或重启。
正式UP1 ELF SHA `8bfb824b9f73967add8d27535bc275f9bcbb9dbbdb671ffaf3bf83edf375d14c`；
UP2 ELF SHA `627545f53ffba3d876973371042c70174c254734f433f01afc1b47578057e660`；原M6/DT保留。
CAN/UART“接线改变，先不要发送”继续有效。

## 实现与限制

- `port/m7_mn.c/.h`：唯一任务串行调用，拒绝其他任务、ISR、IRQ屏蔽和重入；
  COLD→IDLE→PREPARED→IDLE→COLD。没有start/SwReset/SwitchOff/任意发送入口。
  PREPARED保持真实NMT `GsOff`；process按timer→有界EDRV poll→oplk_process顺序泵送。
  状态有owner、最后错误/事件、NMT状态、处理/事件计数；仅owner可取快照，非跨任务接口。
- initialize不占GMAC/timer；**prepare会调用真实硬件acquire/start**，不能当纯只读命令上板。
  当前仅mock RTOS/寄存器边界的原生测试调用prepare；板端须先完成host handoff与P2/P1门槛。
- 复用固定上游CiA302-4 MN OD生成器/模板，不复制Demo_3CN配置。
  OD与核心同样读取`common/oplkinc.h`配置，包含CFM/PDO/ASnd对象。
  标准node-ID表范围254不是254节点容量保证；NodeAssignment默认全0，没有CN/伺服计划。
  初始化参数MN ID=0xF0、软件周期1000us；未NMT reset，无周期性能或外部设备身份承诺。
- 内存CDC固定15字节，仅写本地0x1006=1000，静态生命周期覆盖栈。
  结构预检限16KiB/64项，检查逐项头/长度/溢出/截断/零项/尾随字节；不是任意OD配置的语义认证。
  Native用真实`obdcdc_loadCdc()`验证CDC→OD更新，不是假setter或假对象字典。
- 0003：检查target_init返回值；memmap失败补ctrlu_exit；停止先证明EDRV DMA与highres timer
  静默，再释放任何用户/内核资源；失败保持stack initialized，不继续释放环境。
  **部分初始化或停止失败进入终止FAULT，不自动回滚、不重试、不调用destroy/exit**；
  已分配内存/lease保留到固件重启。这是安全隔离边界，不是完成事务回滚/热故障恢复。
- 0004：OD PRC条件按数值而非仅`defined`判断，FALSE时不宣告/生成PRes chaining支持。
- 0005：故障注入发现DLLK CAL四个MN请求队列分配失败goto Exit时没有设置ret，
  上游会误报创建成功；逐处补`kErrorNoResource`。
- 修复公共prepare构建器的换机缺陷：父Git checkout内解包时，Git apply可能静默跳过全部路径
  并返回0。现隔离Git discovery ceiling并反向检查补丁；新增真实父Git嵌套解包测试。
  P0/P1/P2核心/EDRV/RTOS源代码、0001/0002与配置不改；仅prepare helper/回归测试更新。
  原来正确应用补丁的服务器环境里，旧阶段六个交叉产物逐字节不变。

## 实际验证

最终`checked-final-v2.log`与`checked-repro.log`两个全新输出根：

1. P3a 25组真实完整栈C检查通过：100次prepare/process/stop、1600次分配/1600次释放，
   live=0、无残留mutex/ETH/timer lease、NMT始终GsOff、无TX doorbell或timer arm。
   每个16次分配位置单独失败注入；target/PHY/timer/信号量失败、owner/ISR/IRQ屏蔽拒绝、CDC边界通过。
   DMA停止失败保留16块heap+mutex+ETH/timer lease；timer停止失败已关闭ETH，保留heap/mutex/timer。
   后续prepare/process/stop/exit/init全部拒绝，无二次释放或重新取得资源。
2. 原P0 NMT/OD 2组、P1 EDRV 9组、P2 RTOS 12组通过；累计parser/18生命周期/3codec回归通过。
   Windows/Linux各87项Python通过，包括真实父Git嵌套解包检查。
3. 72个真实核心C+4个移植/应用C+1个真实OD生成器，共77个C全部强制合并到AArch64对象，
   不用gc-sections删除休眠代码冒充完整链接；25 HAL与真实API/OD/app符号存在。
   只余22真实BSP边界+8libc，无FP/SIMD/Linux代理/原子运行库；不是RTOS最终ELF链接。
4. 两独立目录9个库/合并对象逐字节一致，见`repro-report.json`；完整对象960192B，
   SHA `6b5a697045a6bc2ee696471a66e8dabdfdd718a0245d6830081cd54b1a7e6032`。
5. 修复前原始失败/告警日志保留：补丁hunk/上下文、OD宏配置、测试API名称错误，
   及四请求队列分配失败误报成功；`allocation-callsite.log`定位真实申请调用。
   原99条核心warning仍保留，无ASan/UBSan；PASS不等于零告警/生产认证。

SHA256SUMS包含当前scoped输入/证据；旧阶段动态README/memory哈希只能在历史提交校验，
不能拿旧SHA256SUMS校验新增HEAD。正式两个ELF不变；P3a没有新交付固件。

## 换机复现

先按总复现入口下载固定摘要Docker镜像、M6工程/工具链，Git LFS取完整上游tar。
固定环境执行以下命令（不取浮动源码、不访问板卡；输出路径必须不存在）：

```sh
export TOOLCHAIN_PATH=/home/openeuler/build/tl3572-2oo3/toolchain-14.3
export STAGE=/absolute/checkout/stages/stage07-peripheral-partition
POWERLINK_BUILD_ROOT=/new/output/p3a-first bash "$STAGE/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT=/new/output/p3a-second bash "$STAGE/build/build_m7_powerlink_passive_mn.sh"
python3 "$STAGE/tests/compare_powerlink_p3a.py" /new/output/p3a-first /new/output/p3a-second /new/output/repro-report.json
python3 -m unittest discover -s "$STAGE/tests" -p 'test_*.py' -v
bash "$STAGE/tests/run_integrated_native.sh"
```

服务器根`/home/openeuler/build/powerlink-mn-p3a-20261010`，软件根
`build-checked-final-v2`、`build-checked-repro`；`stage`是构建镜像，scoped交付在`delivery`。
GitHub同步/清单验证以最终报告为准，不将本记录自身声明当作上传或验证证据。

## 下一步

P3b：累计UP2 owner任务/有界命令邮箱/跨任务诊断快照，全部MN核心与OD接入同一累计ELF，
默认只创建休眠任务，不调用prepare、不发帧；先做软件重复启停/故障/原接口回归。
随后只测CNTP/PPI30访问/中断/最坏响应与P1 forced100-half物理收发，通过后再开放MN reset。
最后须隔离真实CN互操作、节点配置/PDO/SDO/断线恢复/负载周期测试，才讨论设备控制与实时指标。
