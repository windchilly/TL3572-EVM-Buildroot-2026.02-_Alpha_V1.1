# M7 构建输入与 RPC 修复复建

## POWERLINK MN 核心软件准备入口（2026-10-10）

`build_m7_powerlink_core.sh` 固定解包完整上游源码，运行无硬件原生 NMT/OD 检查，
编译并审计 AArch64 核心库；使用独立 `POWERLINK_BUILD_ROOT`，拒绝覆盖。
这是 P0，不提供硬件 HAL、不部署/发送、不替换累计 ELF。
参见[源码入口](../source/powerlink/README.md)与[实际记录](../tests/powerlink-mn-p0-20261010/README.md)。

后续 P1 EDRV 入口 `build_m7_powerlink_edrv.sh` 保留不变。
当前 P2 软件入口为 `build_m7_powerlink_rtos.sh`；真实累计 UP1/UP2 候选入口
`build_m7_powerlink_rtos_candidate.sh` 会应用 0011/0012 默认关闭补丁，输出仍仅在新源码树内。
这不是可运行 MN，没有部署/定时器或 PHY 访问，也不覆盖 `firmware/`。
完整双目录构建、对比和限制见 [P2 换机复现记录](../tests/powerlink-mn-p2-20261010/README.md)。

## ETH3 主机电源恢复

2026-10-09新增`source/host/eth3_power_enable.py`、`m7-eth3-power.service`与
`build/install_m7_eth3_host.sh`，用于openEuler独占的ETH3专用U21/P02电源初始化。
将三文件放到板端同一目录，以root运行installer；已有不同部署文件会拒绝覆盖。
只初始化GPIO和安装主机服务，不改M6镜像/DT或统一UP ELF，也没有自动加入旧源码归档/Yocto配方。
开机服务已enabled且实际执行/重复启动PASS，板卡冷启动未测；电源首次使能可能引发下游USB Hub重枚举。
完整换板步骤与Linux物理对端验证见[ETH3恢复记录](../tests/board/eth3-recovery-20261009/README.md)。

在固定 M6 构建环境内执行；不能仅靠 Stage07 目录从空系统重建完整镜像。M6 上游源码、工具链和 Yocto 环境的准备步骤见仓库根目录 `repro-inputs/README.md`。

2026-09-28 增加[换机、空目录构建入口](../../../repro-inputs/rk3572/README.md)：
它补齐 libboundscheck 与所有 openEuler 包输入，并从源码构建 UniProton 库；
`m7-mcs` 通过 Yocto 重建依赖和 MCS 包。下文的独立 daemon 快速构建仍要求
已有 M6 sysroot，不等同于该干净构建入口。

## 独立 micad 复建

默认项目根目录 `/home/openeuler/build/tl3572-2oo3`，其中应已有未打补丁的固定 MCS 源码 `src/mcs`（提交 `5cb49156276be04d54a77a630b8600dcc122fdba`）、Arm GNU 14.3 `toolchain-14.3` 及 M6 构建留下的 `build/build-tl3572/tmp/sysroots-components/aarch64/{libmetal,openamp,sysfsutils}`。

在完整仓库克隆内运行：

```sh
bash stages/stage07-peripheral-partition/build/prepare_m7_mcs.sh
bash stages/stage07-peripheral-partition/build/build_m7_micad.sh
```

准备脚本复制上游源码到独立的 `src/mcs-m7`，应用原 M6 的两份补丁及 M7 的 `0003`，不会修改上游目录或 M6 层。若目标目录存在则拒绝覆盖。构建输出默认是 `build-micad-m7/mica/micad/micad`，保留 PIE、RELRO/NOW 和栈保护，并带调试信息；现有上游 UMT 代码仍有一个未使用变量 warning。

可通过 `PROJECT_ROOT`、`MCS_BASELINE_ROOT`、`MCS_ROOT`、`TOOLCHAIN_PATH`、`SYSROOT_COMPONENTS`、`MICAD_BUILD_DIR` 调整路径。记录中的第二次源码准备与编译使用 `mcs-m7-reprocheck` 及 `build-micad-m7-reprocheck`；两个源码树逐文件一致，含调试路径的 ELF 不要求跨构建目录哈希一致。原 M6 依赖库没有重新安装到板卡。

## Yocto 集成边界

`source/yocto/meta-tl3572-m7` 是补充层，依赖原 `meta-tl3572-stage3` 的 `tl3572` collection，只为 `mcs-linux` 增加 `0003`。把本补充层加入**独立 M7 构建配置**的 `BBLAYERS`，保留整个 Stage07 的目录层级；补丁仍从同一份 `source/patches/mcs` 引用。不要单独复制 bbappend 后丢失这个相对路径。

早期只验证元数据解析及独立 daemon 编译。2026-09-28 的[空目录重建检查](../../../repro-inputs/rk3572/tests/clean-rebuild.md)
已通过 M6 镜像 2920/2920 和 M7 MCS 软件包 147/147，实际生成 RPM；独立部署版
micad 也使用本轮新编的依赖库重建，并与实机修复版哈希完全一致。仍未重打完整 M7 镜像，
未把新 RPM 部署到板卡。在已有环境中临时检查新增层解析时，仍可使用
`tests/m7-yocto-parse.conf`（先按实际克隆位置调整其中路径），配合：

```sh
bitbake -r /absolute/path/stage07-peripheral-partition/tests/m7-yocto-parse.conf -e mcs-linux
```

必须同时确认 `BBFILE_COLLECTIONS` 包含 `tl3572m7`，`SRC_URI` 包含 `0003-rpc-shared-log-lifecycle.patch`，且 `FILESPATH` 指向实际补丁目录。仅在 `BBLAYERS` 字符串中看到路径不代表层已加载；后读取选项 `-R` 不适合这个验证。

## UP1 / UP2 CAN 直驱测试固件

`prepare_m7_uniproton.sh` 会安装 CAN 测试源并加入默认关闭的
`M7_CAN_DIRECT_TEST` 构建开关；普通 M7 观测固件不运行 CAN 测试。准备独立 M7 源码后执行：

```sh
bash stages/stage07-peripheral-partition/build/build_m7_can_direct_test.sh
```

脚本为 CPU4/CPU5 分别生成 `tl3572-m7-can-up-a.elf` 和
`tl3572-m7-can-up-b.elf`。它们是临时板级测试固件，不替换 M6/M7 基线 ELF，
也不安装为 AutoBoot。板端配置、带回收的执行器、接线条件和已验证边界见
[CAN 直驱实机记录](../tests/board/can-direct-20260928/README.md)。当前实现只覆盖经典 CAN
轮询数据面；这是保留的历史模式。2026-10-09 新增下述独立 IRQ 模式，
不覆盖历史固件；FD/BRS 的后续切片见下文，最终移交仍须四口、错误恢复及持久 DT/冷启动验收。

### CAN 自主字段初始化 / IRQ 模式（2026-10-09）

需使用包含 `0003-rk3572-can-irq-test-hook.patch` 的当前仓库版本；
旧复现文档固定的 9 月提交不包含这次新增功能。
准备和编译阶段都设置 `M7_CAN_IRQ_TEST=ON`，并使用尚不存在的独立目标目录：

```bash
# 容器内，当前工作目录为完整仓库；M6 基线应已完成库构建。
export M7_CAN_IRQ_TEST=ON
export UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-irq
bash stages/stage07-peripheral-partition/build/prepare_m7_uniproton.sh
bash stages/stage07-peripheral-partition/build/build_m7_can_direct_test.sh
```

准备脚本复制未加 M7 补丁的 M6 树，顺序应用 0001/0002/0003 并安装覆盖源码。
默认不应用 0003；`M7_CAN_IRQ_TEST=OFF` 保持历史轮询/观测路径，已有目录不会覆盖。
编译脚本只接受 ON/OFF；ON 但未准备 IRQ 钩子的源码会拒绝编译。
该脚本是双固件应用构建，不隐式构建 UniProton/libmetal/OpenAMP/boundscheck 库。

换机的库输入都已归档；按 [RK3572 空目录入口](../../../repro-inputs/rk3572/README.md)
完成 Git LFS、固定 Docker 摘要和 `run.sh prepare`，然后执行：

```bash
bash repro-inputs/rk3572/scripts/run.sh m6-up
docker exec -e M7_CAN_IRQ_TEST=ON \
    -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-irq \
    "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/prepare_m7_uniproton.sh
docker exec -e M7_CAN_IRQ_TEST=ON \
    -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-irq \
    "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/build_m7_can_direct_test.sh
```

输出位于该源码树 `demos/rk3572_mica/build/tl3572-m7-can-irq-up-a.elf` 和
`tl3572-m7-can-irq-up-b.elf`。仍为 AutoBoot=no 的临时测试，不替换 M6 或原 CAN ELF。
本轮两棵独立源码树各自重新编译双应用，`objcopy -O binary` 后运行镜像逐字节一致；
复用已有 M6 库，没有再次执行空目录库/Yocto 全量构建。完整日志及哈希见
[IRQ 实机与复建记录](../tests/board/can-irq-20261009/README.md)。

板端先确认 FD1↔FD3 接线、无真实执行器、原两实例 Offline、CPU4/5 OFF、
修复版 micad 正常，以及 `/usr/libexec/m7/up_log_reader.py` 已安装。
把两 IRQ ELF、`tests/board/up-{a,b}-m7-can-irq.conf`、
`run_can_direct_pair.py`、`run_can_irq_pair.py`、`can_resource_preflight.py`、
`run_can_irq_with_cpu_load.py` 放到板卡 `/root/m7-can-irq-20261009/`，不放到 MICA AutoBoot 目录。
以板端 root 执行：

```bash
python3 /root/m7-can-irq-20261009/run_can_irq_pair.py
python3 /root/m7-can-irq-20261009/run_can_irq_with_cpu_load.py
python3 /root/m7-can-irq-20261009/run_can_irq_pair.py --stop-a-first
```

每次执行器会运行期解绑 CAN1/CAN3、保存并故意改变自己的时钟/复位字段，
所以不能在正在承载业务流量的系统上运行。失败时也尝试回收；若任一 CPU OFF 未确认，
不写回资源、不重绑 Linux，应保留日志并人工恢复，不自动重启板卡。
测试日志中的最终 `CLEANUP PASS` 与数据面 `OVERALL PASS` 必须同时成立。

### CAN FD / BRS 模式（2026-10-09）

使用当前仓库新增的 `prepare_m7_can_fd.sh`、`build_m7_can_fd_test.sh`，
不要使用固定 9 月提交或仅解压旧 Stage07 tar。与原轮询/IRQ 源码树分开准备：

```bash
# 固定容器内，M6 源码及全部库已完成构建；目标目录必须不存在。
export UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-fd
bash stages/stage07-peripheral-partition/build/prepare_m7_can_fd.sh
for profile in 0 2 4; do
    M7_CAN_FD_PROFILE="$profile" bash stages/stage07-peripheral-partition/build/build_m7_can_fd_test.sh
done
```

准备脚本内部启用 IRQ，依次应用 0001/0002/0003/0004，安装独立 FD C 与 codec 头。
FD 编译脚本显式启用 DIRECT/IRQ/FD；`M7_CAN_FD_PROFILE` 只接受 0/2/4，默认 0。
CMake 的 `M7_CAN_FD_TEST` 默认 OFF，原准备/构建脚本和默认观测/轮询路径不改变。
各 profile/CPU 使用独立应用目录；输出在 `$UNIPROTON_ROOT/demos/rk3572_mica/build/`：
`tl3572-m7-can-fd{0,2,4}-up-{a,b}.elf` 共六份。这些是临时测试 ELF，不能直接代替业务固件。

换机先按 [空目录入口](../../../repro-inputs/rk3572/README.md) 完成 Git LFS、固定 Docker
摘要、`run.sh prepare`、`run.sh m6-up`，再对该容器执行：

```bash
docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-fd \
    "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/prepare_m7_can_fd.sh
for profile in 0 2 4; do
    docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-fd \
        -e M7_CAN_FD_PROFILE="$profile" \
        "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/build_m7_can_fd_test.sh
done
```

本轮实际在两棵新源码树重新编译六应用，运行镜像逐字节一致；复用已有 M6 库，
不是新一轮全部库/Yocto 空目录构建。源码、时序计算、实测 ELF hash、构建日志和边界见
[CAN FD/BRS 记录](../tests/board/can-fd-20261009/README.md)。原 IRQ 的历史文档/固件总清单
校验对应 `077f93b`，新增 FD 另立校验记录，不回写旧证据。

板端沿用 FD1↔FD3 隔离接线、CPU4/5 OFF、原实例 Offline、Linux CAN DOWN、修复版
micad 与独立内存日志读取器等前置条件。把六 FD ELF 和六份
`tests/board/up-{a,b}-m7-can-fd{0,2,4}.conf` 放到 `/root/m7-can-fd-20261009/`，同时放入：

- `run_can_fd_pair.py`、`run_can_fd_with_cpu_load.py`；
- 共用 `run_can_direct_pair.py`、`run_can_irq_pair.py`、`run_can_irq_with_cpu_load.py`、`can_resource_preflight.py`。

配置为 AutoBoot=no，不安装为开机启动；从该目录以板端 root 执行：

```bash
python3 /root/m7-can-fd-20261009/run_can_fd_pair.py --profile 0
python3 /root/m7-can-fd-20261009/run_can_fd_pair.py --profile 2
python3 /root/m7-can-fd-20261009/run_can_fd_pair.py --profile 4
python3 /root/m7-can-fd-20261009/run_can_fd_with_cpu_load.py --profile 4 --stop-a-first
```

profile0 为 FD 不变速，2/4 为 BRS 约 2/4 Mbit/s，仲裁均 500 kbit/s。
执行器会逐阶段检查 16/32/64 字节、RX 原始 FDF/BRS/DLC、总字节数、时序读回和本核 IRQ，
不能仅依据经典 CAN PASS 宣称 FD 成功。每次必须同时有 `OVERALL PASS` 与 `CLEANUP PASS`。
运行期间临时操作 own CRU/IOC/IRQ 并解绑 Linux，不能在业务系统直接运行。
CPU OFF 未确认时不恢复资源/不重绑/不自动重启，保留日志人工处理。
此版本仅 FD1/FD3 单请求在途的测试切片，尚无四口、故障恢复、冷启动或工业协议验收。

## UP1 / UP2 RS-232 直驱测试固件（2026-10-09）

使用独立源码树，不能在已有 CAN/FD 树叠加：准备器复制未加 M7 补丁、已构建库的
M6 基线，应用 0001/0002/0003/**0005**（不应用 CAN FD 的 0004），安装 UART C/codec。
`M7_RS232_TEST` 默认 OFF，与 CAN DIRECT 模式互斥；应用构建显式关闭 CAN。
原 M6、CAN 轮询/IRQ/FD 源码树和固件均不覆盖。

```bash
export UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs232
bash stages/stage07-peripheral-partition/build/prepare_m7_rs232.sh
for baud in 115200 38400 9600; do
    M7_RS232_BAUD="$baud" bash stages/stage07-peripheral-partition/build/build_m7_rs232_test.sh
done
```

输出六份 `$UNIPROTON_ROOT/demos/rk3572_mica/build/tl3572-m7-rs232-{115200,38400,9600}-up-{a,b}.elf`。
这些是 1000 个固定 32 字节请求/应答的临时测试 ELF，不是业务协议或生产队列驱动。
选择 xin24m/div1，UART 整数除数为 13/39/156，8N1；计算速率均比标称高约 0.1603%。
Linux/RPMsg 只启停和读日志，不转发串口字节；RBR/THR 收发仅在各 UP 本核 ISR。

换机需当前 Git 提交及 LFS 输入，先按 [空目录入口](../../../repro-inputs/rk3572/README.md)
完成固定 Docker 摘要、`run.sh prepare`、`run.sh m6-up`，再对该容器执行：

```bash
docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs232 \
    "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/prepare_m7_rs232.sh
for baud in 115200 38400 9600; do
    docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs232 \
        -e M7_RS232_BAUD="$baud" \
        "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/build_m7_rs232_test.sh
done
```

这组脚本仅重编应用，库由 M6 全源码入口生成；不是一次新的完整 Yocto/内核构建。
旧 9 月 Stage07 tar 不含本功能，应使用当前跟踪补丁/覆盖层，不回写历史归档。

板上 UART4/T4/R4 是 UP1 的 SoC UART4/ttyS4，**板上 UART3/T3/R3 是 UP2 的
SoC UART8/ttyS8**；J4-1(T4)→J4-5(R3)，J4-4(T3)→J4-2(R4)，仅隔离接线，不接执行器。
先确认原 up-a/up-b Offline、CPU4/5 OFF、修复版 micad 和独立内存日志读取器正常，
两串口没有进程占用。六 ELF、六 `up-{a,b}-m7-rs232-*.conf` 及下列脚本放到
`/root/m7-rs232-20261009/`，不要安装到 AutoBoot 目录：

- `run_rs232_pair.py`、`run_rs232_with_cpu_load.py`、`rs232_resources.py`；
- 共用的 `run_can_direct_pair.py`（仅生命周期/日志助手）、`can_resource_preflight.py`（仅 GIC 地址助手）。

```bash
python3 /root/m7-rs232-20261009/run_rs232_pair.py --baud 115200
python3 /root/m7-rs232-20261009/run_rs232_pair.py --baud 38400
python3 /root/m7-rs232-20261009/run_rs232_pair.py --baud 9600
python3 /root/m7-rs232-20261009/run_rs232_with_cpu_load.py --baud 115200
python3 /root/m7-rs232-20261009/run_rs232_pair.py --baud 115200 --stop-a-first
```

执行器解绑 UART4/8，保存 own CRU/IOC/GIC 状态后故意关闭 own 时钟、保持复位、置分频/16，
由 UP 初始化。只有两 CPU OFF 确认后才恢复资源/rebind；不自动重启。
每轮必须同时有数据 `OVERALL PASS` 和 `CLEANUP PASS`，失败日志也保留。
只适用于不承载业务的隔离测试窗口；实际结果及未验证项见
[RS-232 实机记录](../tests/board/rs232-20261009/README.md)。

## UP1 / UP2 RS-485 直驱测试固件（2026-10-09）

保持UP1=SoC UART1/CPU4，UP2=SoC UART2/CPU5。按手册板号分别为UART2、UART1；
板号与电气网名的差别、方向脚/RTSN语义及原始证据见
[RS-485记录](../tests/board/rs485-20261009/README.md)。用户需确认两口A↔A、B↔B、
隔离参考地连接，仅安全隔离对接，不接执行器；不是短接A/B或交叉TX/RX。

`prepare_m7_rs485.sh`内部调用RS-232准备器，复制完整M6源码及已有库，依次应用
0001/0002/0003/0005/0006（不应用0004），再安装独立RS-485 C，复用CRC codec。
原RS-232驱动/固件不修改。`M7_RS485_TEST`默认OFF，与CAN/RS-232互斥。
新目标目录必须不存在；脚本不覆盖M6、CAN、RS-232树，也不重建内核/Yocto/库。

```bash
export UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs485
bash stages/stage07-peripheral-partition/build/prepare_m7_rs485.sh
for baud in 115200 38400 9600; do
    M7_RS485_BAUD="$baud" bash stages/stage07-peripheral-partition/build/build_m7_rs485_test.sh
done
```

输出六份`$UNIPROTON_ROOT/demos/rk3572_mica/build/tl3572-m7-rs485-{115200,38400,9600}-up-{a,b}.elf`。
两路8N1，24MHz/整数除数13、39、156，计算波特率比标称高约0.1603%，不是仪器测量。
MCR=0物理RTSN高/TX，MCR=2物理RTSN低/RX；由UP手动换向，不使用Linux GPIO代理。
只有ISR读RBR/写THR；发送后等TEMT，切回RX。单请求在途、32字节带序号CRC的1000次请求/应答，
不是Modbus/生产队列、自动RTS换向或长时实时性验收。

换机先按[全源码入口](../../../repro-inputs/rk3572/README.md)完成固定Docker摘要/LFS输入、
`run.sh prepare`及`run.sh m6-up`生成M6库，再在固定容器运行上述两个脚本，例如：

```bash
docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs485 \
    "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/prepare_m7_rs485.sh
for baud in 115200 38400 9600; do
    docker exec -e UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs485 \
        -e M7_RS485_BAUD="$baud" \
        "$REPRO_CONTAINER" bash /repo/stages/stage07-peripheral-partition/build/build_m7_rs485_test.sh
done
```

本轮两独立树各编六应用，运行镜像逐字节一致；复用M6库，未再次全量Yocto构建。
旧Stage07 tar不回写，应克隆包含0006的当前提交，不能只解压旧归档。

原up-a/up-b须Offline、CPU4/5 OFF，修复版micad及独立内存日志读取器正常，
UART1/2无进程、非console，方向脚GPIO0_D3/GPIO2_B6未被其他用户申请。
六ELF、六份`tests/board/up-{a,b}-m7-rs485-*.conf`与以下脚本放到`/root/m7-rs485-20261009/`：

- `run_rs485_pair.py`、`run_rs485_with_cpu_load.py`、`rs485_resources.py`；
- `run_can_direct_pair.py`（仅生命周期/日志助手）、`can_resource_preflight.py`（仅GIC地址助手）。

配置AutoBoot=no，不放入开机自动启动目录，以板端root执行：

```bash
python3 /root/m7-rs485-20261009/run_rs485_pair.py --baud 115200
python3 /root/m7-rs485-20261009/run_rs485_pair.py --baud 38400
python3 /root/m7-rs485-20261009/run_rs485_pair.py --baud 9600
python3 /root/m7-rs485-20261009/run_rs485_with_cpu_load.py --baud 115200
python3 /root/m7-rs485-20261009/run_rs485_pair.py --baud 115200 --stop-a-first
```

执行器临时解绑Linux，保存CRU/IOC/GIC，故意关own clock/保持reset/改错clock selector，
再由UP恢复。两CPU OFF后才还原资源/rebind，OFF未确认时不自动重启或恢复。
每轮必须同时有`OVERALL PASS`、`CLEANUP PASS`和方向计数通过；原始失败日志也需保留。
不改持久DT，不触碰UART0/ETH1；只能在无业务的隔离测试窗口使用。

## 当前开发入口：UP1 / UP2 统一增量固件（2026-10-09）

CAN经典/FD/BRS、RS-232、RS-485、独立保留日志与RPMsg诊断控制已合并为两个ELF。
上述单项构建仍可恢复历史证据，但后续开发/交付默认使用此入口。
换机先按[完整恢复入口](../../../repro-inputs/rk3572/README.md)取得固定Docker摘要、LFS输入及工具链，
执行`run.sh prepare`、`run.sh m6-up`生成完整M6树和库，再在固定容器、目标不存在的目录执行：

```bash
export UNIPROTON_ROOT=/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated
bash stages/stage07-peripheral-partition/build/prepare_m7_integrated.sh
bash stages/stage07-peripheral-partition/build/build_m7_integrated.sh
bash stages/stage07-peripheral-partition/tests/run_integrated_native.sh
```

若仓库挂载为`/repo`，须在容器中先`cd /repo`，或使用上述脚本的`/repo/...`绝对路径。
准备器复制M6全树/库，应用0001/0002/0003/0007，安装overlay，再用0008适配复制的驱动、0009修复启动；
当前再叠0010增加UP2 ETH2资源与驱动；不叠加旧0004/0005/0006，不覆盖旧树/ELF。
输出位于`$UNIPROTON_ROOT/demos/rk3572_mica/build/`：

- `tl3572-m7-integrated-up-a.elf`：CPU4/SGI8/image 0x7b200000/MMU 0x7ba00000；
- `tl3572-m7-integrated-up-b.elf`：CPU5/SGI9/image 0x7c200000/MMU 0x7ca00000。

`M7_INTEGRATED_FIRMWARE=ON`，旧启动自动测试开关OFF；默认不初始化或收发工业外设。
CAN模式与串口波特率均由RPMsg显式运行时命令选择。该通道只控制测试/回报状态，实际数据仍由UP ISR直驱。
控制源码/累计驱动使用`-Werror`；其他M6代码的既有警告不在本次修复范围。
仅统一目标任务上限8→16，当前四工作任务各16KiB栈；旧任务上限/构建不改变。
0009仅统一目标页表预算32→64KiB；Start必须检查mmu_init返回值，失败记录原始内存日志并请求CPU_OFF，
不再进入OS/RPMsg。正常启动逐项验证真实PTE，且回读SCTLR/TTBR0/TCR/MAIR后才启动应用。
构建末尾强制运行页表预算与ELF启动CBNZ分支核验；任一失败，脚本返回非零，产物不可部署。

两独立目标目录各运行上述准备/构建，再比较运行镜像（ELF调试路径导致文件hash不同）：

```bash
bash stages/stage07-peripheral-partition/build/verify_m7_integrated_repro.sh FIRST_BUILD_DIR SECOND_BUILD_DIR
python3 stages/stage07-peripheral-partition/tests/verify_integrated_elf.py
```

ELF静态脚本核验仓库`firmware/`下两个交付文件；本轮复用M6库，不是重新全量构建Yocto/内核/OS库。
临时配置`up-{a,b}-m7-integrated.conf`为`AutoBoot=no`，修复板端路径为`/root/m7-integrated-mmu-fix-20261009`，
没有更改原M6实例或开机自启配置。被动执行器`tests/board/run_integrated_passive.py`硬性禁止M7 run，
调用只读实际页表核验；部署助手清单、命令与四轮结果见[MMU修复记录](../tests/board/integrated-mmu-fix-20261009/README.md)。
不能直接套用旧单项自动执行器。物理run仍须重新确认隔离接线并完成统一独占移交。
运行时命令/资源分配见[原软件合并记录](../tests/board/integrated-20261009/README.md)，该记录须在17024db复查旧输入。

2026-10-10 ETH增量：同一对累计ELF增加`M7 run eth 0/64/1514`（只允许UP2），
`run all`不含ETH；ETH数据由UP2轮询DMA直驱，RPMsg仍仅控制。UP2增量映射MAC/GRF和自身非缓存DMA。
临时共享电源/根时钟辅助模块在匹配内核构建树生成：

```bash
bash stages/stage07-peripheral-partition/build/build_m7_eth2_power_hold.sh
```

默认原项目路径含kernel-src-pristine、build-kernel和toolchain-14.3；
换机先执行换机入口的m6-image，再通过TL3572_KERNEL_SRC/TL3572_KERNEL_BUILD指定
linux-tl3572配方实际源码/已编译目录(B=S)。模块输出默认项目build-m7-eth2-power-hold，
不在只读仓库源码旁写生成物；可用M7_ETH2_MODULE_BUILD_DIR指定独立输出目录。
不得在不同内核直接加载仓库6.12.69模块。辅助只持共享NVM0电源及根时钟，不代理MAC/PHY/DMA数据。
当前实测ELF/ko、两树复建脚本、固定哈希及预检/受控收发流程见[ETH2直驱记录](../tests/board/eth-direct-20261010/README.md)。
旧被动执行器保留历史固定ELF与命令白名单，不能直接用于ETH增量版本。

## 板卡部署与回退

POWERLINK P1 的软件构建与休眠累计候选由 `build_m7_powerlink_edrv.sh` 和
`build_m7_powerlink_candidate.sh` 提供；必须选择新输出目录，不写正式 firmware/，不部署板卡。
候选编译真实 UP2 EDRV/BSP，但没有 MN 启动命令；P2 target/timer 尚未实现。
命令、双目录复编与实际证据见 [P1 软件记录](../tests/powerlink-mn-p1-20261010/README.md)。

本轮板卡部署采用独立文件 `/usr/libexec/m7/micad` 和持久 drop-in `/etc/systemd/system/micad.service.d/90-m7-rpc-fix.conf`，原 `/usr/bin/micad` 未覆盖。drop-in 内容来自 `source/host/micad-m7-rpc-fix.conf`。服务仍使用原 PIDFile、MCS 内核模块前置依赖及失败重启策略。临时 M7 配置为 `AutoBoot=no`，没有安装为开机自动启动实例。

需要回退时，先停止所有 UP 实例，并用 `tests/board/query_cpu_off.py 4 5` 确认两 CPU 真正 OFF；然后仅移走上述 `90-m7-rpc-fix.conf`，执行 `systemctl daemon-reload`、`systemctl restart micad`，服务即恢复 `/usr/bin/micad`。不要移走原 `10-mcs-km.conf`。若任一 CPU 未 OFF，不能用守护进程重启代替板卡恢复，也不要继续测试旧版已知有问题的双停止路径。

回归脚本 `tests/board/regress_micad_rpc_lifecycle.py` 需要在板卡上与 `query_cpu_off.py`、Stage06 的 `tests/dual-runtime-regression.py` 放在同一目录（或用 `--echo-helper` 指定）。先创建两份临时 M7 配置并保持 Offline，再执行脚本；它覆盖两种停止顺序及交替启动、真实 RPMsg 回显、进程 PID/自动重启数、PSCI OFF、共享日志 fd 数及离线 fd 基线。失败时中止，不会自动重启板卡或在异常状态继续压测。
