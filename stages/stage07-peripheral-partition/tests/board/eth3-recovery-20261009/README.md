# ETH3 专用电源恢复与 Linux 物理对端验收（2026-10-09）

结论：`ETH3 ENUMERATION+100M FULL-DUPLEX+LINUX PHYSICAL L2 PASS`。
开机电源服务已安装、启用并实机执行成功；重复启动服务不再次切换已使能的 GPIO。
本轮不重启，不把服务重启冒充冷启动验收；ETH2 的 UP2 直驱仍未实现/未测试。

## 范围和根因

用户要求先测 ETH2，随后确认用网线连接板上 ETH2↔ETH3；本轮最新要求为“先解决ETH3”。
CAN/RS-232/RS-485 的“接线已改变，先不要发送”限制不解除。
开始时 Linux 只有 ETH1=`eth0`、ETH2=`eth1`；USB 没有 SR9900，虽内核已内置并注册 `sr9900`。
U21 的专用电源使能 P02 未配置为输出低；使能后 SR9900 立即枚举并成功绑定，证实问题是
缺少板级电源初始化，不是需要额外驱动模块或 SR9900 固件。

硬件依据：

- [原厂测试手册](../../../../../docs/manuals/2-1-评估板测试手册.pdf)第69–70页，
  3.14.3节要求导出 GPIO517 并设输出；原厂截图也显示下游 USB Hub/Bouffalo 重枚举。
- [底板原理图](../../../../../hardware/carrier-board/TL3572-EVM评估底板原理图/TL3572-EVM-A1.1-000-SCH-202609021543.pdf)
  第15页：U21/P02 经 R278 控制 Q18 的 PMOS 栅极，低电平打开 `VDD_3V3_ETHU1`，为 U46/SR9900AI 供电。
  该网名虽写 `ETH2_PWRON`，实际连接本页 ETH3(USB)，不得据网名误操作 GMAC1 的 PHY reset。
- 当前 U21=`I2C1/1-0020`，gpiochip base=515，offset=2，所以全局号517；
  U22/P07 是另一路共享 Hub reset（当前 GPIO538），本脚本不写它。

没有调用共享 Hub reset，**但实际通电引发一次下游 Hub 和未绑定驱动的 Bouffalo 设备重枚举**。
不得描述为所有 USB 设备完全不受影响。通电前未挂载 USB 存储，没有已绑定的 USB 业务设备；
ETH1 的有线 SSH、地址、默认路由和 micad 均保持正常。

## 实现和板端部署

新增输入：

- `source/host/eth3_power_enable.py`：默认只读；显式 `--enable` 才操作 GPIO。
  通过 gpiochip 的标签、真实 I2C1 设备路径和16位宽确认 U21，动态计算 base+2，不盲用517。
  只通过 gpiolib sysfs 导出本脚，不直接写 I2C/整组寄存器；GPIO已被占用即失败。
  要求 sysfs `active_low=0`，用 `direction=low` 原子设置输出和物理低电平；
  已是 out/0 时不再写。读取回验并等待唯一 `sr9900` 网络接口，失败不反复断电或重置 Hub。
- `source/host/m7-eth3-power.service`：oneshot + RemainAfterExit，开机等待 GPIO/USB 枚举；
  不停 micad、不操作 PHY、接口地址或路由，停止服务不关闭已经使能的 ETH3。
- `build/install_m7_eth3_host.sh`：显式板端安装，已有不同文件拒绝覆盖；
  安装 `/usr/libexec/m7/eth3_power_enable.py` 和 `/etc/systemd/system/m7-eth3-power.service`，
  执行 daemon-reload、enable/start，检查真实 Loaded/Active/Result 状态。

板端调试目录 `/root/eth3-recovery-20261009`，服务安装并启用。
原 M6 内核、DT、boot/rootfs 镜像和两份统一 UP ELF未替换；本轮没有重新编译 Yocto/内核/UP。
当前是独立主机服务部署，不宣称服务已打入旧归档或重建的全 M7 镜像。
服务重复启动两次都成功，USB 设备编号仍保持 Hub=5、SR9900=6、Bouffalo=7，没有再次重枚举。
`install-first.log`保留首次因板端缺 `systemd-analyze` 而在文件安装前停止的原始结果；
随后 installer 在工具缺席时用实际 systemd 单元加载/执行结果验证，最终`install.log`成功。
Windows 初次单测因测试夹具创建符号链接权限不足失败，随后改用目录模拟 resolved device；
生产安全检查未削弱。新增11项单测及全部53项 Stage07 Python 单测最终通过。
已镜像到构建容器`/home/openeuler/build/eth3-recovery-20261009/repo`，初版23项SHA均通过，
Linux下同样11项新增单测及installer Bash语法通过，见`linux-checks.log`。
`linux-checks-first.log`保留第一次把宿主卷根误当作项目根而cd失败的结果；随后按实际挂载路径核验成功。

## 链路和物理收发结果

ETH2=`eth1`/GMAC1/`2a040000.ethernet`，ETH3=`eth2`/SR9900/USB `1-1.4.1`，
VID/PID=`0fe6:9900`，驱动`v1.12.13`，MAC=`00:e0:9a:42:ba:eb`。
启用 `eth2` 后，两端都为 `carrier=1 / 100Mb/s / Full`。没有新增静态 IP、路由、桥接或网络命名空间；
既有 `20-wired.network` 的 DHCP/IPv6 行为保持，因此出现自动链路本地地址/后台报文，不能声称零以太网发送。

`eth3_l2_smoke.py`仅在显式 `--confirm-board-loop` 后发送本地实验 EtherType `0x88b5` 帧；
核对 GMAC1、唯一板载 SR9900、双端100M全双工，绝不使用 `eth0`。
通过 AF_PACKET 在两端直接发送/接收，检查目标/源 MAC、角色、序号、完整数据模式和 CRC32，
排除 PACKET_OUTGOING 本地副本，不使用可能本机短路的 IP ping。

| 轮次 | 64B帧（不含FCS） | 1514B帧（不含FCS） | 结果 |
|---|---|---|---|
| 电源使能后 | 每方向1000帧 | 每方向1000帧 | 完整内容/序号/CRC PASS |
| 安装服务并重启服务两次后 | 每方向1000帧 | 每方向1000帧 | 完整内容/序号/CRC PASS |

合计每方向4000帧、3,156,000原始帧字节；两端最终 rx/tx_errors、rx/tx_dropped均0。
不同驱动的 Linux rx_bytes统计口径不同，不用其代替原始帧校验或外部吞吐仪器。
ETH1累积的历史 drop计数不属于本轮测试对；不宣称全板网络计数均0。
退出时 ETH2/ETH3 保持链路 UP，为后续 ETH2 测试提供 Linux 对端。

最终 ETH1=`192.168.2.141/24`，默认路由仍走`eth0`；micad PID311、active、NRestarts0；
两原 UP 实例仍 Offline，boot_id=`91f20083-69fc-4bdb-9008-c621eb8b43e7`不变，failed units0。
仅作 Linux↔Linux 物理对端验证，**不是 UP2 GMAC/MDIO/DMA/IRQ/PHY直驱成果**。
本轮未重启/刷写、未操作 CAN/UART、未解除之前工业发送限制，也未启动任一 UP。

## 换机/换板复现

内核需已含 `CONFIG_USB_NET_SR9900=y`、Python3及systemd，使用对应 TL3572 底板。
将上述两份`source/host`文件和`build/install_m7_eth3_host.sh`完整复制到板端同一目录，然后：

```sh
python3 /root/eth3-recovery-20261009/eth3_power_enable.py
bash /root/eth3-recovery-20261009/install_m7_eth3_host.sh /root/eth3-recovery-20261009
systemctl status m7-eth3-power.service
lsusb -t
```

需要物理对测时，先确认 ETH2↔ETH3 专用网线、无外部网络或现场执行器，
识别实际接口归属并启用 SR9900 接口，再复制两份`tests/board/eth3_*`助手：

```sh
python3 /root/eth3-recovery-20261009/eth3_recovery_snapshot.py
python3 /root/eth3-recovery-20261009/eth3_l2_smoke.py
python3 /root/eth3-recovery-20261009/eth3_l2_smoke.py --confirm-board-loop
```

解除开机自动电源初始化：`systemctl disable --now m7-eth3-power.service`；
这不会立即关闭电源或删除源码，若后续要关闭/改回 GPIO 输入，需另确认 USB/ETH3 业务是否可中断。
没有实测冷启动、拔插、长时间压力或千兆性能；ETH3百兆对端不能证明 ETH2 千兆能力。
下一步回到 UP2 的 ETH2 驱动与统一固件增量实现，保持 ETH1 和新 ETH3 Linux 对端。

证据含 before/after/final JSON、电源和服务日志、两轮 L2 原始结果、内核 USB 事件与单测日志；
本目录 `SHA256SUMS`只列本轮不可变输入/证据，不纳入后续不断追加的memory/首页索引。
