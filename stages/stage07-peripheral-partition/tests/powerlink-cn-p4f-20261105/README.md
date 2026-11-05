# P4f Linux 软件 CN 启动前检查与窗口存储（2026-11-05）

结论：P4f 软件验证通过，交付“只读预检/离线重放 + 一次性窗口存储”组件。**没有 CN 启动器**，不连接或运行真实 CN；所有 PASS 都保持 `runtime_ready=false`、`execution_allowed=false`。原 P4e C 源码及双架构库不改、不重编，UP2/P3j 的 no-CN/拒绝 RX 条件不变。

本轮未连接 `192.168.2.141` 或 COM7、移交 ETH2、运行 CN/demo/help、发送网络/CAN/串口帧、重启或改正式配置。仅连接 `10.100.60.226` 的 `dev_openeuler` 做软件验证。最近实板记录仍是 11 月 4 日 P3j-v2 历史归还状态，不是本轮重采样。

## 新增组件

| 文件 | 作用 |
| --- | --- |
| `tests/board/powerlink_cn_preflight.py` | 纯数据检查、packet 表和 ELF/版本解析，无导入 IO |
| `tests/board/collect_powerlink_cn_preflight.py` | 只读本地采集或显式离线重放，不调用栈、不创建窗口 |
| `tests/board/powerlink_cn_window.py` | Linux root 专用锁/永久标记存储，无网络或执行/恢复入口 |
| `config/powerlink-cn-preflight.template.json` | 默认不可用模板：boot/ns/MAC/设备/ELF/运行库均未填，检查立即拒绝 |

### 预检门槛

- 固定 Linux/aarch64/M6 内核、root/CAP_NET_RAW、明确 boot ID 和 net/pid/user namespace，拒绝 LD_ 注入环境。两次观察须同身份、同进程起始时间、同网络及运行库；总采样跨度 ≤5s，数据末端距校验 ≤2s，时间重叠、过期、变化均拒绝，不自动重试。
- CN 只允许 eth2/SR9900/板载 `1-1.4.1:1.0`，完整设备 realpath、ifindex、单播 MAC 须显式钉死。管理 eth0 与 `192.168.2.141/24`、原 driver/MAC/地址及双栈路由须保持选定基线，不能把管理口当 CN。
- CN 必须干净 UP/LOWER_UP、MTU1500、非桥/绑定/VLAN/上层依赖、无已附着 XDP/promisc/tc ingress/egress filter。任何 IPv4/IPv6 地址，包括 link-local，都拒绝；IPv4/IPv6 **全部路由表**及多路径 nexthop 引用 eth2 都拒绝。不自动删地址、关 IPv6、停 DHCP、调整网卡或路由来满足检查。
- 严格解析 9 列 `/proc/net/packet`；eth2、所有接口或未绑定的 AF_PACKET socket 即拒绝，协议 0/尚未收包也不例外。另检查已知 CN/MN/demo/抓包/旧网络测试进程及未来候选 basename，记录 PID+starttime，进程退出/不可见/PID复用直接拒绝。无主动 kill/关闭其他人的 FD。
- 只读命令按完整 argv 白名单限制为固定 `ip -j` 查询、`tc -j filter show`。采集需本地 Linux root 且显式完整策略；本轮只用模拟 sysfs/proc/命令验证采集器，没有在板上或构建机上运行完整真实网卡采集。
- 候选和 libc/loader 的路径、SHA 显式钉死；逐级 no-follow/root-owned 路径、非他人可写的 regular 文件、单链接、大小上限、前后 inode/size/mtime/ctime 一致。readelf 通过持有的 FD 读同一 inode，检查 ELF64/little-endian/AArch64、解释器、非可执行栈、无 RPATH/RUNPATH/AUDIT 等注入项。
- 当前静态 ABI 子集仅支持候选直接依赖 libc，加 libc/loader 的闭合依赖；按每个 provider 的 **精确 symbol-version 集合**匹配，不把“GLIBC 版本号更大”当作支持所有符号。拒绝原未受限 P4a demo 的名字及完整 SHA（改名仍拒绝）。这不是完整符号重定位/运行时兼容证明。

Linux 文档说明 `/proc/net` 只代表当前网络 namespace，故不能把一次全局抓包表当作系统强制独占；参见 [proc_pid_net(5)](https://man7.org/linux/man-pages/man5/proc_pid_net.5.html)。packet 列语义按 [Linux v6.12 packet_seq_show](https://github.com/torvalds/linux/blob/v6.12/net/packet/af_packet.c) 处理。运行库只用文件/ELF 静态读取，不使用可能执行目标的 ldd，也不运行 loader `--list`；参见 [ldd(1)](https://man7.org/linux/man-pages/man1/ldd.1.html)。

### 一次性窗口存储

仅是未来调用方的组件，不提供 CLI，不获取/推断人类授权，也不调用 arm/init/exec。调用者必须在任何外部动作前取得成功 claim，并另外满足全新隔离授权及预检。

1. 要求预先准备的 Linux root-owned 0700 公共目录，逐级 no-follow 打开；祖先不得他人可写（root sticky 祖先允许），最终目录不是宽泛根路径。固定公共 `LOCK` 必须为 root 0600 单链接空 regular 文件，使用非阻塞排他 flock，FD 为 CLOEXEC。
2. 同一公共目录中，任何类型的 `HOLD`（包括损坏软链接/部分文件）阻止所有新 window ID。不能根据进程已死、旧 PID 不存在、重启或上次退出码自动放行。
3. 先 O_EXCL 创建 `ATTEMPTED-<UUID>`，完整写入并 fsync 文件/目录，再 O_EXCL 写 HOLD 并 fsync。记录绑定 boot、≤2s claim 有效期、策略/快照/候选 SHA；调用者无法在 fsync 期间改写已复制的记录。短写/fsync/到期/未知结果保留已有文件，不 unlink、truncate 或重试。
4. `Window.close()` 只关闭本进程持有的锁/目录 FD，不清除 ATTEMPTED 或 HOLD。当前刻意没有归还/清除 HOLD 的 API，直到真实栈静默证明接入。HOLD 创建前失败时原 window ID 已消费，组件尚未返回、不得执行 CN；不能把失败当作已经获准的新窗口。

[flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html) 是协作锁，不是对不合作进程、root 或网卡的强制排他。fsync 测试不是实板掉电/存储持久性认证；正式路径、文件系统、跨重启持久性及配套永久主机标记仍须在受限启动器中审查。

## 验证结果

- Windows/Linux **各 434 项 Python**：原 380 +新 54，通过。新场景包括纯门槛、ELF/packet 严格解析、完整只读采集链的模拟边界、PID复用/CPU计数变化、历史 USB device 几何，以及默认模板拒绝。
- 构建机 root 执行 **19 项真实 Linux 文件/锁/子进程/FD 检查，各运行两次，共38 PASS**：并发子进程抢占失败、进程 `os._exit` 后 HOLD 仍阻止重用、close 不清标记、软/硬链接/权限漂移、旧 ATTEMPTED、短写、fsync 失败、落盘后过期、过期请求零文件写入；另验证真实归档 AArch64 ELF 用受控 FD +四次 readelf 读取、对象变动/错 SHA/软链接拒绝。x86 构建机没有对应 ARM loader，正例的 loader realpath 显式模拟，不是 ARM 运行库实测。
- Windows/Linux 最终重放：**1 个仅证据正例 +32 个拒绝变异**，三份 JSON 逐字节相同；身份/boot/namespace/IP/IPv6/route/多路径/XDP/tc/raw socket/程序/版本/budget/改名 demo 等都 fail-closed。所有身份和候选 SHA 为明确的合成测试数据，不是许可或可部署配置。
- 最终 Linux 日志记录构建机 x86_64/root 环境及 **10 个实际输入 SHA**。历史源/产物检查和新清单继承所有 P4e 输入，原库保持 Native `490956B/f0c7e1e9...`、AArch64 `454204B/a29e046a...`，没有新 C 编译或执行。

## 保留的中间结果

`linux-native-first.log` 的19项初次通过和第一版合成重放保留。`windows-first.log` 为429项中间通过，`windows-targeted-first.log` 的53项夹具因 Windows 分隔符/模拟 resolve 值失败（1 failure/3 errors），`windows-second.log` 保留路径夹具仅剩1处失败，修正后 `windows-third.log` 的433项中间通过；最终再补历史设备路径场景成为434项。

复核历史实板快照发现 sysfs `device` 指向 USB interface，不能假设以 `/net/eth2` 结尾；已修正本轮新检查并加历史几何回归。第一版合成文件仍在旧 `windows-replay/`、`linux-replay/` 中保留，最终以 `*-replay-final/` 为准，不能把中间合成路径当作实板记录。

`linux-final-first.log` 两遍19项及重放已通过，但434项回归因新历史快照依赖未上传而失败，原日志和第一输入锁保留。补入 `tests/board/eth3-recovery-20261009/final.json` 的完整复现闭包后，在新远端 replay 目录复测，最终10输入/434项/两遍19项通过；没有删测试或改写失败。

## 换机复现（只在构建环境）

先校验本目录 SHA256SUMS，然后在仓库根运行：

```sh
python3 -B -m unittest discover -s stages/stage07-peripheral-partition/tests -p 'test_*.py' -v
python3 -B stages/stage07-peripheral-partition/tests/run_powerlink_cn_preflight_replay.py /path/to/new-synthetic-replay
```

构建机 Linux root 可另运行两次 `tests/check_powerlink_cn_window_linux.py`，只操作每个测试新建的 `/tmp/m7-cn-p4f-*`，测试退出清理自身夹具；生产窗口模块本身从不清理永久标记。不要将此命令作为板卡 CN 启动步骤。源恢复复用原固定1355文件/P4e变换，在新目录核对原25生成 SHA，不重编/替换库。

服务器独立 `/home/openeuler/build/powerlink-cn-p4f-20261105`；`verify_powerlink_cn_p4f_checkpoint.py` 只核验归档/输入 SHA、重做合成 replay、运行 Python 离线回归和恢复不变 P4e 源，不调用真实采集器/窗口 claim/C/CN/板卡。GitHub及服务器后验日志排除在本阶段自身清单外，完成后单独提交，来源提交和精确清单数量见日志。

## 尚未完成，不能越过的门槛

这不是可运行 CN 前端或独占证明。后续仍需将上述模块接入**有界单 owner CN 启动器**，加入独立人类授权/主机永久标记、fresh 再核验、候选 FD 执行绑定、正式持久存储/内存栈/信号/停止证明和 HOLD 归还协议。当前只限制软件逻辑预算，未执行真实周期；链路速率/双工、运行库实际加载/重定位和板端工具适配需和新 MN profile 一起验证。严格采集可能因 DHCP 寿命字段/进程变动而拒绝，禁止自动改网络或盲重试。

再准备独立 CN-capable 有界 UP2 MN/decoder、匹配 CDC/PDO/过程映像及事件处理；不能放宽旧 P3j no-CN 条件来接从站。全部软件准备完成后才申请新的隔离物理窗口；不等待采购，也不把合成 PASS 当实板验收。
