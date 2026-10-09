# 统一固件 MMU 容量与启动检查修复（2026-10-09）

结论：`MMU BOOT FIXED / BUILD+REPRO+STATIC+PASSIVE BOARD PASS / PHYSICAL TEST STILL PAUSED`。
用户授权修复页表容量与启动检查，但“接线已改变，先不要发送”仍有效。
本轮没有M7 run、CAN/串口工业测试数据、外设解绑、重启、刷写、持久DT修改或原M6覆盖。

## 为什么旧版本通过、合并后才出现

`historical-budget.json`在替换原两ELF之前读取真实符号/映射，记录旧文件哈希：

| 固件 | UP1需求 | UP2需求 | 原预算 |
|---|---:|---:|---:|
| CAN IRQ、CAN FD/BRS单项 | 28KiB | 28KiB | 32KiB |
| RS-232单项、RS-485单项 | 28KiB | 28KiB | 32KiB |
| 修复前统一固件 | 36KiB | 32KiB | 32KiB |

4KiB外设映射自身很小，但不同2MiB地址区域需要不同的L3页表，另有根表与L2表。
合并所有现有工业外设映射后，UP1共9张表，超过原8张容量；UP2的UART2/RS-485与UART8/RS-232
共用同一L3区域，所以比UP1少1张。不是物理接线改变导致，也不是原已测协议突然失效。

启动代码原本忽略mmu_init错误，导致UP1仍在MMU关闭状态下进入RPMsg，libmetal未对齐128位写异常。
编译、两树运行镜像一致及无MMIO单测只证明软件生成/控制逻辑一致，不证明真实页表分配/启动成功；
原ELF静态检查仅查声明的映射，漏查容量。这是此次合并引入的回归和验证缺口。
原始故障证据见[上一轮记录](../integrated-passive-20261009/README.md)，固定提交
`a16ad2c1a2798e227655ce92fb3e4b794c347ce4`；原软件/两ELF固定`17024db864070b655dc94a4530ae59baec3fb6c7`。
两份历史清单与原始日志不回写，复查须checkout对应提交并git lfs pull，不用当前修复文件套旧hash。

## 修复内容

新补丁`../../../source/patches/uniproton/0009-rk3572-integrated-mmu-boot-guard.patch`仅由统一准备器应用：

- 统一目标页表32→64KiB，保留原MMU区域基址；不扩大外设映射、不改变设备归属。
- Start调用mmu_init后用CBNZ w0跳到MmuBootFatal，失败不进入OsResetVector或RPMsg。
  原始错误日志只用标量volatile读写、不依赖格式化libc或SIMD；置offline后走现有AMP使用的PSCI SMC CPU_OFF。
  如CPU_OFF返回，保持中断屏蔽停在WFE，不继续运行应用。
- 成功建表后、启用MMU前检查48个真实终端PTE的地址与属性；早期结果存非零初始化.data，
  避免后续BSS清零。正常main再回读SCTLR、TTBR0、TCR、MAIR，一致才进入OS配置。
- 每次启动输出`[boot] MMU PASS ...`；构建末尾强制页表预算、64KiB链接符号、.data结果以及
  CBNZ w0真实机器码/目标地址校验。失败返回非零，留下的中间ELF不可部署。

历史0001–0008、单项源码/固件、M6/Yocto/内核不改。不是增加打印或只对齐shm_device掩盖异常。
新的错误分支请求CPU_OFF未在实机上强制触发，只有静态分支/调用路径核验，不能称故障注入PASS。

## 正式交付与独立复现

当前仓库`firmware/`保留UP1/UP2各一份统一ELF，包含此前CAN经典/FD/BRS、RS-232、RS-485和诊断；
各接口仍显式运行时触发、默认passive，不拆回单项交付。旧失败版本由Git/LFS历史恢复。

| ELF | SHA256 |
|---|---|
| tl3572-m7-integrated-up-a.elf | 2575faeaa01aaa76c63229d07e190bcdda9f49ac2ef3b0eb60e152ef291ae399 |
| tl3572-m7-integrated-up-b.elf | b0ae2ad5af68aaa2a85f6b9229fecfe26738baf48b88890d2c2ff94b1ef083dc |

固定Docker摘要/LFS完整M6输入、工具链恢复过程沿用[换机入口](../../../../../repro-inputs/rk3572/README.md)。
完成run.sh prepare/m6-up后，按[当前统一构建入口](../../../build/README.md)在新目标目录prepare/build。
顺序为完整M6+0001/0002/0003/0007+overlay+0008/0009，不叠加旧0004/0005/0006。
容器dev_openeuler最终两棵新树：

```text
/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-mmu-fix-v2-20261009
/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-mmu-fix-repro-v2-20261009
```

每树独立准备并构建两应用；复用M6 UniProton/securec/libmetal/openAMP库，非全量Yocto或库重建。
实际交叉Arm GNU14.3.1、CMake3.27.9；CMakehost探测GNU12.3.1不代表应用用了host编译器。
`build-inspection.log`保留实际flags、库hash、启动/错误分支/标量日志反汇编。
`build-final-v2.log`包含两棵新树构建、自动预算/ELF检查、两对objcopy镜像比较及17组native检查。
运行镜像哈希：UP1 `efc11569958cf08c859bd0771407403c25449ecf3929adbc0d59573b9f24a3bc`，
UP2 `2dff36a94872ec5594402f6dbdf197b50d365392f31f0c74421712b14f8a8ae6`，两树逐字节一致。
ELF调试路径不同，不能宣称跨目录完整ELF一致。
本目录`build-and-reproduce.sh`完整执行两树prepare/build/比较/native检查；换机仓库挂载为/repo时，
可设置`STAGE_ROOT=/repo/stages/stage07-peripheral-partition`，用新的`REPRO_TAG`避免已有目录。
默认路径/标签对应上述最终实验；已有目录会拒绝覆盖，不删除旧SDK或历史树。

中间失败也保留：`build-first.log`为0009 main.c上下文缺旧CAN条件块的apply --check失败；
此时0009未应用，修正context后复用已准备到0008的树，`build-final.log`成功，第二树`build-repro.log`成功。
最终v2仅给Start补函数大小，便于静态检查真实CBNZ机器码；运行代码不变，重新准备两棵新树验证全过程。
既有M6 proxy/libc及RWX段链接警告保留，不宣称全工程零警告。

## 四轮被动实机回归

板端独立目录`/root/m7-integrated-mmu-fix-20261009`，配置AutoBoot=no，不安装为开机自动实例。
将两ELF、两conf、以下助手放在该目录：

```text
run_integrated_passive.py  integrated_mmu_resources.py
verify_integrated_elf.py   audit_integrated_mmu.py
run_can_direct_pair.py    can_resource_preflight.py
rs232_resources.py       rs485_resources.py
query_cpu_off.py         dual-runtime-regression.py（Stage06）
```

执行：`python3 /root/m7-integrated-mmu-fix-20261009/run_integrated_passive.py --cycles-per-order 2 --echo-count 100`。
执行器硬性白名单仅M7 status、M7 unsupported与普通M6虚拟echo，禁止所有run。
`run-01-passive-fixed.log`四轮全部OVERALL/CLEANUP PASS，覆盖A→B/B→A启动及A→B/B→A停止。
每路累计400次451字节虚拟echo、191200响应字节，M7状态/非法命令及第一路停止后的幸存实例查询通过。

每轮两实例均SCTLR=`0x30d01805`（M/C/I开启），UP1为9/16页、UP2为8/16页，TTBR0为各自固定基址。
`integrated_mmu_resources.py`只读实例保留DRAM，不读控制器FIFO：Linux读取实际页表与早期.data结果，
逐条核验全部48个终端PTE、页表指针范围、地址/属性、实际页数和成功返回码；不是只查ELF声明。
所有pending/running/done/rc工作计数0，无工业驱动begin日志。
启动有正常GIC CPU接口/SGI初始化；执行器不写CRU/IOC/外设SPI、不解绑，不是完全无MMIO启动。

`preflight.log`、`final-state.log`确认原up-a/up-b Offline、CPU4/5 PSCI OFF、临时客户端/ttyRPMSG清理，
六工业控制器Linux绑定、所测CRU/IOC/外设SPI快照不变，micad PID311 active/NRestarts0、failed units0、ETH1正常。
boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7`不变，无重启或原M6覆盖。
另一处create/rm MCS fd泄漏仍在：本轮57→59；四轮start/stop内部离线fd集合未漂移，不能称全局无泄漏。

## 本地核验与下一步

`unit-tests.log`为42项Python通过，含原UP1映射32KiB失败/64KiB成功、错误PTE/表指针拒绝、
MMU日志/外设命令白名单验证；`elf-validation.log`与`fixed-budget.json`为当前正式两ELF静态通过。
从仓库根目录核验本轮独立清单：

```text
sha256sum -c stages/stage07-peripheral-partition/tests/board/integrated-mmu-fix-20261009/SHA256SUMS
python -m unittest discover -s stages/stage07-peripheral-partition/tests -p "test_*.py" -v
python stages/stage07-peripheral-partition/tests/verify_integrated_elf.py
```

`audit_history.py`运行时比较当前ELF；保存的historical-budget.json是在替换原统一固件之前生成，
回查该旧集成预算须使用17024db两ELF，不能用当前修复hash冒充历史输入。
修复与被动回归完成，下一步仍要重新确认安全隔离接线，才允许同一对固件做工业单项/组合/并发回归。
尚未验收物理集成收发、强制启动故障注入、任意时刻取消、持续工业协议、实时性、持久DT/冷启动或M7.0。
SARADC/ETH2未加入，FD2/4仍按用户选择SKIPPED。
