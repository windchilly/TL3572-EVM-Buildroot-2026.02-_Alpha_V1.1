# CAN 自主初始化 / 中断收发：实施前资源核验

2026-10-09，板卡 `192.168.2.141`，原 M6 运行镜像。以下是当日实施前的只读核验：
**采集本快照时没有编译/部署新固件、没有发送 CAN 帧**。
构建连接随后恢复，后续自主配置/IRQ 三轮通过的证据另见
[CAN IRQ 实机记录](../can-irq-20261009/README.md)，本目录原始快照不回写。

原始结果：[preflight.json](preflight.json)。采集脚本：
[`can_resource_preflight.py`](../can_resource_preflight.py)。脚本只用只读映射访问
CRU、IOC 和 GICD 的指定状态寄存器；不读有消耗副作用的 CAN RX FIFO，
不写 MMIO/sysfs，不改变接口、驱动绑定、MICA 配置或启动镜像。

## 板端核验结果

- `up-a/up-b` Offline；Linux online=`0-3,6-7`、offline=`4-5`。
- `micad` PID=311、active、NRestarts=0；四路 CAN 均 DOWN；ETH1/SSH 正常。
- CAN1/CAN3 仍绑定 Linux `rk3576_can`，尚未持久移交。
- 两路 baudclk 实际为 GPLL 1,188 MHz / 4 = **297 MHz**；HCLK 为 198 MHz。
  生效 DT 的 `assigned-clock-rates=200000000` 不能当作实测时钟。
- 两路引脚复用均匹配生效 DT；相关时钟门未关闭，复位未保持。
- SPI 153/155 对应 INTID **185/187**。两路 GIC target byte 均为 `0x01`，
  已使能、优先级 `0xa0`、电平触发；采集时没有 pending/active。
  `0x01` 是当前 Linux 路由，不代表 UP4/UP5 路由已完成。
- IGROUPR 读数为 0。安全组寄存器在当前访问视图中的可见性未验证，
  不能据此推断物理安全组归属。UP 的实际 CPU target mask 也尚未验证。

## 自主初始化所需的位级边界

以下地址由归档的完整 Stage06 内核源码与生效 DT 交叉核对。
CAN 控制器复用 `rk3576_can.c`，但 **CRU/IOC 必须使用 RK3572 的表**。

| 资源 | UP1 / CAN1 / FD1 | UP2 / CAN3 / FD3 |
|---|---|---|
| MMIO | `0x2ab10000` | `0x2ab30000` |
| 引脚 | GPIO4_B6/B7，mux=13 | GPIO1_D5/D6，mux=13 |
| IOC mux 寄存器 / 本实例 mask | `0x2608608c` / `0xff00` | `0x2608203c` / `0x0ff0` |
| 波特率时钟选择/分频寄存器 | `0x26090404`，bits 13:7 | `0x26090408`，bits 13:7 |
| 该时钟当前字段 | parent=0/GPLL，divider=4 | parent=0/GPLL，divider=4 |
| CLKGATE_CON11 | `0x2609082c`，bits 9/10 | `0x2609082c`，bits 13/14 |
| SOFTRST_CON11 | `0x26090a2c`，bits 9/10 | `0x26090a2c`，bits 13/14 |
| GIC INTID | 185 | 187 |
| GIC target byte | `0x2a6018b9` | `0x2a6018bb` |

源码定位（都在 `repro-inputs/all-stages/stage06-kernel-6.12.69-complete.tar.gz`）：

- `drivers/clk/rockchip/clk-rk3572.c`：CAN1/3 的 parent、divider 和 gate 字段。
- `drivers/clk/rockchip/rst-rk3572.c`：CAN1/3 的两条 reset 的寄存器位。
- `drivers/clk/rockchip/clk.h`：RK3572 CLKSEL/CLKGATE/SOFTRST 基础 offset。
- `drivers/pinctrl/pinctrl-rockchip.c`：`rk3572_pin_banks` 与 4-bit mux 地址计算。
- `arch/arm64/boot/dts/rockchip/rk3572.dtsi`：CRU=`0x26090000`、IOC=`0x26072000`。

实现时使用 Rockchip HIWORD mask 只修改本实例字段，不做共享寄存器整字
read-modify-write，不改 GPLL/CPLL、共享总线根时钟或其他 CAN 通道。
两路 SPI 的 target/priority 同处一个 32-bit word，应按独立 byte 操作；
config/group 涉及共享 word 时，需要明确序列化及 Linux 访问边界。
UP 启动后读取本核 banked ITARGETSR 来确定自身目标位，不能仅由 Linux CPU
编号推算；测试必须验证实际 IRQ 到达本核、TX/RX 中断计数和停止后的 IRQ 清理。

## 实施前验证和已解除的连接阻断

本地执行：

```text
python -m unittest discover -s stages/stage07-peripheral-partition/tests -p 'test_*.py' -v
```

13/13 PASS，其中新资源解码单测 5 项、原 CAN 编码单测 3 项、日志单测 5 项。
这些单测验证地址/位字段解码，不代表硬件中断或自主初始化通过。

既定构建机 `10.100.60.226` 的宿主机 22 和容器 2005 端口均在 SSH banner
返回前关闭连接；PuTTY 和 Paramiko 两种客户端结果一致。板端到构建机的一次
ICMP 检查也未收到回复（不能据此单独断言服务器关机）。板卡无 GCC/CMake，
当时无法在既定构建环境编译新固件，并向用户请求确认服务器/IP/Docker 状态。
没有修改构建机或新建替代构建环境。

恢复构建入口后，从独立 M7 源码树继续：自主 CRU/IOC 初始化与最小设备映射
→ 各自 CAN SPI handler/路由 → 临时双 ELF 构建 → 当前 FD1↔FD3 接线实测
→ CPU4/5 OFF、GIC 状态恢复、Linux CAN rebind 和 micad/ETH1 回归。
持久 DT 移交及冷启动验收仍须另行完成，不以运行期 unbind 替代。

之后连接恢复，在同一构建机独立源码树完成编译、复建核验及板卡测试；
原固件和历史证据未覆盖。本快照与后续源码/日志一起保存到主仓库。
