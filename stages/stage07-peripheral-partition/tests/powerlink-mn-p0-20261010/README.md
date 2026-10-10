# POWERLINK MN / P0 软件准备（2026-10-10）

状态：**P0 软件检查通过；不是可运行主站，也没有板端 POWERLINK 验收**。
用户选定 UP2 MN，保持 ETH2 独占方向及累计固件策略。未连接板卡 SSH/串口，
未发送物理帧，未解绑网卡、改变链路模式、重启、刷写或替换正式 ELF/DT。

## 完成内容

- 上游 V2.7.2 完整 1355 个跟踪文件，无子模块；包括源码、工具、示例、文档和版权声明。
  Git commit `048650a80db37fa372330c3a900d2c8edb327e47`，tree `0d33af5588578055f5f112167170c67115a19d13`。
- 归档 `source/powerlink/upstream/openPOWERLINK_V2-2.7.2.tar.gz`，6062267 字节（约5.78 MiB），
  SHA256 `d342b8cd2b8a743a077c3b8cd1e262f0d6f9f8a5f0d8b49f4b14197e945fa381`。
  归档 SHA/长度/Git commit/文件数在解包前核验，拒绝覆盖及不安全成员；不在线追随 master。
- UniProton LP64/little-endian targetdefs、同地址空间 direct/local/no-OS CAL、MN/PDO/ASnd-SDO/CFM 核心。
  禁用 Socket/UDP、虚拟网卡、文件配置和冗余；CDC 以后由内存提供。
- 实际编译 72 个上游 C 文件，逐个保留 BSD 文件头并记录源码哈希。
  全归档包含其他平台许可证文件；BSD 文件头检查不是整包法律许可或协议符合性认证。
- AArch64 GCC14.3/Cortex-A53/general-registers-only/strict-align/no-outline-atomics，
  ELF64 小端可重定位核心；静态库 634932 字节。
  最终库 SHA256 `d16139c8181e033f49af145823da7960f721f2b03cb25cef99dfd0674997117b`。
- 原生 MN NMT 测试：21 次真实上游状态转换，覆盖启动、两种 PreOp2 门控事件顺序、
  Operational、周期错误、内部通信复位、冲突 MN、关停和无效事件；DLL/用户事件仅为观察桩。
- 原生 OD 测试：整数上下界保持检查，越界及不支持的浮点范围写入不改变数据，
  无范围 REAL32 原始字节搬运。REAL32/64 范围检查拒绝，不支持浮点计算。
- 审计：仍有25个 HAL 和8个 libc 符号未解析；没有 Linux/socket/pcap/pthread/文件 IO/libatomic 依赖，
  反汇编未发现 FP/SIMD 指令。未提供假成功硬件实现；当前库不能直接链接为可运行 MN。
- Windows 67 项 Stage07 Python 检查通过（原55+新12）；容器新增12项通过；两项原生 C 测试通过。

## 两次独立复编

构建机 `10.100.60.226` 的 `dev_openeuler`，CMake3.27.9、Python3.11.6，
native GCC12.3.1，AArch64 GCC14.3.1。固定 Docker/工具链恢复方式沿用项目复现入口。

容器交付准备目录：`/home/openeuler/build/powerlink-mn-p0-20261010/stage`。
两次最终全新展开/编译目录：`build-checked`、`build-checked-repro`，各自包括完整解包源码、
native 测试、AArch64 核心、compile_commands 与 JSON 审计。
`checks-final-success.log` 确认整个静态库和合并的可重定位对象都逐字节一致，
不是仅比较部分符号或只重用第一次的目标文件。

换机先获取 Git LFS 源码包，并按[完整项目入口](../../../../repro-inputs/rk3572/README.md)
恢复固定 Docker/工具链。仓库须包含本轮 POWERLINK 入口，不能 checkout 到历史 M6 固定点后执行。
在容器中（假设仓库挂载 `/repo`）：

```sh
export POWERLINK_BUILD_ROOT=/home/openeuler/build/powerlink-mn-p0-new-machine
export TOOLCHAIN_PATH=/home/openeuler/build/tl3572-2oo3/toolchain-14.3
bash /repo/stages/stage07-peripheral-partition/build/build_m7_powerlink_core.sh
```

输出目录必须不存在；默认也拒绝覆盖。只读源码目录支持，所有编译产物写入独立输出目录。
构建不需要访问板卡，不启动 micad，不调用 CAN/UART/ETH 物理测试。

## 原始失败与限制（均保留）

- `build-first.log`：上游 targetsystem blob 为 CRLF，Linux 下 LF 补丁严格上下文不匹配；
  改为校验固定归档后 `git apply --ignore-space-change`。
- `build-second.log`：旧上游 fallthrough/array-bounds 告警被最初的全局 `-Werror` 拒绝。
  当前保留告警输出，继续将隐式声明、指针类型、整数转换和返回类型错误设为阻断；
  新测试仍全局 `-Werror`。没有声称消除了这些上游告警；生产候选前必须审查。
- `build-third.log`：测试误认为周期错误会清除 PreOp2 两项门控标记；与上游实现不符。
  修正测试为两次独立启动验证事件顺序，未修改 NMT 逻辑。
- `build-fourth.log`、`build-final.log`、`build-repro.log`：早期成功构建，
  后两次 .a 因 ar 时间戳不同，合并对象一致；改用 ar/ranlib 的确定性归档参数。
  确定性归档首轮证据为 `build-verified.log`、`build-verified-repro.log`；补齐关键类型告警阻断后，
  最终证据为 `build-checked.log`、`build-checked-repro.log` 及两个 core-audit JSON。
- `repro-and-python-linux.log`：一致性检查已通过，随后调用不存在的 `aarch64-none-elf-size` 停止；
  换为实际库长度检查后完整运行结果在 `repro-and-python-linux-final.log`，exit0。
- `checks-final.log`：最终两目录一致性和新12项 Python 通过；随后尝试 ASan/UBSan，
  但容器缺少 libasan/libubsan，CMake 编译器探测无法链接。未安装或更改固定构建环境，
  sanitizer 测试未执行，不能宣称通过。非 sanitizer 最终检查在 `checks-final-success.log`，exit0。

EDRV、target/RTOS、高精度 timer、PHY 半双工、板端周期收发、CN 互操作、集成实时性、
持久资源移交均未完成。PHY/GMAC 直驱底座的历史 L2 通过不能升级为 POWERLINK PASS。
下一检查点见[路线](../../docs/m7.0-powerlink-mn-roadmap.md)。
