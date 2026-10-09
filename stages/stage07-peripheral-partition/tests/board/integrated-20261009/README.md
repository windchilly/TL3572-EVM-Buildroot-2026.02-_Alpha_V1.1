# M7.0 两份统一固件：软件合并记录（2026-10-09）

结论：`SOFTWARE MERGED / BUILD + REPRO + NATIVE + ELF STATIC PASS / NOT DEPLOYED`。
本轮按用户“你先合并即可”要求，仅在本机及euler构建容器合并软件，没有连接板卡、
部署固件、解绑外设、发送测试帧、重启、刷写或修改DT。历史单项实机PASS不等于集成PASS。

## 交付内容与归属

每版本只有UP1/UP2各一份ELF，功能累积加入，不再按接口、波特率或CAN profile生成不同交付镜像。

| 功能 | UP1 / CPU4 | UP2 / CPU5 | 运行时选择 |
|---|---|---|---|
| CAN经典、FD、FD/BRS | CAN1 / 板上FD1 / 0x2ab10000 | CAN3 / 板上FD3 / 0x2ab30000 | classic、FD不变速、BRS约2/4 Mbit/s；仲裁500 kbit/s |
| RS-232 | SoC UART4 / 板上UART4 / 0x2c160000 | SoC UART8 / 板上UART3 / 0x2c1a0000 | 9600 / 38400 / 115200，8N1 |
| RS-485及RTSN换向 | SoC UART1 / 手册板号UART2 / 0x26500000 | SoC UART2 / 手册板号UART1 / 0x2c140000 | 9600 / 38400 / 115200，8N1；UP手动MCR/RTSN换向 |
| 保留内存日志 | 原UP1日志区域/读取器 | 原UP2日志区域/读取器 | 从启动汇编起保留，正常运行不占UART4/8 |
| 诊断控制 | 原UP1 RPMsg TTY | 原UP2 RPMsg TTY | 读状态、选测试及参数；不代理物理外设数据 |

两串口每次仍是1000个32字节请求/应答；经典CAN每次10000次请求/应答；FD每次16/32/64字节
各1000次请求/应答。这些是已有驱动的有限测试入口，不是持续工业应用/Modbus/生产协议栈。
CAN FD2/FD4保持用户选择的`SKIPPED / 未验证`，不新增其驱动映射；SARADC和ETH2尚未加入。

交付文件位于`../../../firmware/`（Git LFS），两份总计1,350,560字节，约1.29MiB：

| 文件 | SHA-256 |
|---|---|
| `tl3572-m7-integrated-up-a.elf` | `d22bdf200c326e2727d4c9ff9f19e4aa46c38727b3b7b7dedc7f33503fbf1581` |
| `tl3572-m7-integrated-up-b.elf` | `1a4ece0cff536cfe5f796b1aecc843fc04b7ffb3ad5243ca094dba99b84fa622` |

UP1仍CPU4/SGI8/image 0x7b200000/MMU 0x7ba00000；UP2仍CPU5/SGI9/image 0x7c200000/MMU 0x7ca00000。
共享内存/RPMsg/日志布局不变，两份`../up-{a,b}-m7-integrated.conf`为`AutoBoot=no`，未安装到板卡。

## 同一固件的运行时入口

默认启动`mode=passive`，只建立诊断及工作任务，不调用工业外设初始化或发送测试帧。
普通M6 RPMsg echo保留；以下命令通过对应实例的原RPMsg TTY发送：

```text
M7 status
M7 run can 1
M7 run can 0
M7 run can 2
M7 run can 4
M7 run rs232 115200
M7 run rs485 38400
M7 run all 115200 4
```

CAN `1`为经典CAN、`0`为FD不变速、`2/4`为FD/BRS profile；串口接受三个已验证档位。
`all UART_BAUD CAN_PROFILE`同时排队三类工作，两个串口用同一指定波特率；单项命令可独立选择各串口档位。
每条命令必须是一条完整RPMsg消息（建议一次write），最多63字节，可带结尾CRLF；
不支持拆包重组、多命令同包、二进制或嵌入换行。控制命令不携带CAN/串口业务载荷。

回复`ACCEPTED mask=...`仅表示排队成功，不等于硬件测试PASS。
`status`给出`pending`、`running`、`rc=CAN/RS232/RS485`及`done=...`累计完成次数。
初始`rc=0`但`done=0`表示尚未测试；需等待工作完成，核对模块结束码与原始驱动计数/日志。
CAN经典/FD共享一个工作槽，同类重入返回`ERROR busy`；组合请求遇到任一选中模块忙则全部拒绝，不部分启动。
三个工作任务可独立推进，队列操作采用本核中断锁；每任务16KiB静态对齐栈。

安全前提：固件无法从裸机内部判断Linux是否仍持有外设。发送任何`run`之前，必须完成
安全隔离对端接线、Linux资源独占/解绑、原实例Offline与CPU4/5 OFF、修复版micad及日志预检。
不得在Linux驱动仍绑定相同控制器时调用`run`；同一对端两UP应使用匹配参数及时启动相应测试。
本轮没有提供或运行自动资源移交/实机组合执行器；旧单项执行器依赖启动自动测试，不能直接替换ELF照用。
有限测试会超时退出并清理own IRQ；未实现任意时刻取消、永久驱动服务或故障自动恢复。

## 合并方式与资源核验

新鲜完整M6树+0001/0002/0003，随后0007接入统一CMake/main/MMU/RPMsg控制入口，
安装历史驱动及新控制overlay，再用0008仅修改复制出的四驱动。**不叠加0004/0005/0006**。
已验证的历史overlay、补丁、ELF、日志、tar不修改；新入口是
`../../../build/prepare_m7_integrated.sh`、`build_m7_integrated.sh`。

0008将FD profile/串口baud转为运行时参数，参数错误在MMIO前返回，导出不同CAN函数名，
每次清零自己的计数/队列；关闭外设/SPI、清pending后删除自己的OS IRQ注册，恢复自己的target/priority。
这使同一固件可重复调用及切换CAN模式；该生命周期变化仍需下一轮实机回归。
UART busy状态计入失败，避免仅凭其他计数判PASS。

仅统一目标任务上限从8扩到16。M6内核通过`OsTskRegister`动态设置`g_tskMaxNum`，
AMP TCB按该值动态分配，故可复用原库；两ELF `OsTaskInfoSet`反汇编均为`mov w1,#16`。
共享CRU/IOC使用原hiword-mask写入，GIC target/priority用原字节写，enable/disable/pending用own SPI W1S/W1C。
这是软件字段约束，不是硬件位级隔离；并发与跨核行为没有在本轮验收。

每UP的7个4KiB设备RW/XN页（除此之外仅原image/RPMsg/log及GIC16KiB）：

- UP1：`26074000 26086000 26090000 260b0000 26500000 2ab10000 2c160000`；
- UP2：`26074000 26082000 26084000 26090000 2ab30000 2c140000 2c1a0000`。

无UART0或GPIO bank新增映射。共享根总线/晶振仍由平台提供，外设页映射不等于持久DT移交。

## 可复现过程与证据

换机按[完整输入入口](../../../../../repro-inputs/rk3572/README.md)获取固定Docker摘要/LFS输入，
先`run.sh prepare`、`run.sh m6-up`，再按[统一构建说明](../../../build/README.md)构建两ELF。
必须克隆本次提交的0007/0008/控制源码，不能只使用合并前的Stage07历史tar。
本轮容器`dev_openeuler`实际构建目录为：

```text
/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-final-v2-20261009
/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-repro-20261009
```

每棵树编两个应用，实际交叉编译器Arm GNU 14.3.1，CMake3.27.9。
原库哈希与实际编译flags/启动调用/任务配置见`build-inputs-final.log`。
复用M6 UniProton、securec、openAMP、libmetal库，未再次全量构建内核、Yocto或OS库。
CMake初始探测显示host GNU12.3.1，但实际flags/link使用交叉14.3.1，不按探测行认定编译器。

两对`objcopy -O binary`运行镜像逐字节一致（`build-repro.log`）：

- UP1：`18dc328d54ece127aa5255eaa706a310117b7a4823afabeac3fb60df9c198d00`；
- UP2：`4e2de168b56073bfb462308bb87358194fc4d3635145d74b5cafe4568a33f967`。

ELF含不同源码目录的调试路径，跨目录ELF文件hash不同，不宣称完整ELF字节一致。
`../../../build/verify_m7_integrated_repro.sh`可重新比较两个build目录。

`../../run_integrated_native.sh`以native GCC C11 `-O2 -Wall -Wextra -Werror`执行17组无MMIO检查：
1组有界解析、UP1/UP2各7组调度/任务失败清理、2个历史CRC/FD codec；日志为`native-tests-script.log`。
这不模拟真实GIC/CRU/ISR时序或真正抢占并发。
`../../verify_integrated_elf.py`仅Python标准库，核验两交付ELF的AArch64、四驱动/控制/日志符号、
三工作栈及精确MMU设备页。既有31项Python单测和上述静态检查见`validation.log`。

保留全部中间失败：`native-tests-first.log`为未初始化局部变量的-Werror失败，现已零初始化；
`build-prepare-first.log`为零context配置补丁不能git apply，已补上下文并新树构建；
`build-inputs-first.log`为核验脚本最后grep无匹配而非编译失败，现已核验动态TCB来源；
`build-first.log`为配置修正前两初版构建，不作为交付。最终构建见`build-final-v2.log`。
统一控制/四驱动均-Werror通过；M6 libc/proxy既有警告及RWX链接段警告仍保留，未宣称全工程无警告。

本目录`SHA256SUMS`固定本次输入/输出/脚本/记录；可变memory/索引需在本次固定提交核验。
旧RS-485的66项清单仍对应`6f0b5587e32fc92bc49c6114172a2c9c2864c7fd`，不回写历史证据。

## 下一步与验收边界

用户要求继续测试后，先适配统一资源预检/控制执行器，再在**同一对ELF**完成被动启动/诊断、
单项回归、三接口组合/并发、CAN模式切换与串口改档、重复执行及双实例两种停止顺序。
待这些通过后继续增量加入SARADC/ETH2，不恢复单接口独立固件路线。
本轮未测集成实机、持续协议、外部独立对端、实时性、任意取消、持久DT/冷启动或完整M7.0。
原M6固件/配置不变；另一处全局`mcs_fd` create/rm泄漏仍未修复。
