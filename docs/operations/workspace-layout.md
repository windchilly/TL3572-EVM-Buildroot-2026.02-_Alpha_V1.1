# 本地与 openEuler 工作区目录规范

## 本地仓库

```text
TL3572-EVM(Buildroot-2026.02)_Alpha_V1.1/
├─ README.md                    项目入口与分类索引
├─ memory.md                    当前状态与交接历史
├─ hardware/                    硬件规格、核心板/底板设计、数据手册
│  ├─ specifications/           核心板、底板、本板配套附件规格
│  ├─ core-board/               引脚、机械/位号图、2D/3D 与封装
│  ├─ carrier-board/            原理图、PCB、BOM、机械/位号图
│  ├─ datasheets/               SoC、核心板/底板元件数据手册
│  └─ design-guides/            硬件说明与底板设计指南
├─ software/                    厂商源码、工具链、示例、参考固件
│  ├─ sources/{kernel,u-boot,buildroot}/  完整厂商源包
│  ├─ toolchains/               固定 Arm GNU 14.3
│  ├─ examples/                 CAN/串口/GPIO、通信、音频与 GUI 示例
│  └─ firmware/{kernel,u-boot,rootfs,updateimg}/  原厂参考/回滚产物
├─ stages/stage01-...stage07-*/  各阶段设计、实现、参考固件、正式记录
├─ repro-inputs/                完整复现输入、固定摘要/提交、构建脚本
│  ├─ all-stages/               当前全阶段恢复入口
│  ├─ rk3572/                   共享包输入与 M6/M7 干净构建入口
│  ├─ stage01-05/               原始上游快照和幸存历史输入
│  └─ meta-tl3572-stage3/ ...    原始 M6 层及配置，保留兼容路径
├─ docs/                        技术与项目文档
│  ├─ project/                  总移植路线
│  ├─ manuals/                  厂商使用/开发/评估测试手册
│  ├─ reference/rockchip/       完整技术参考、补丁、SBOM
│  ├─ vendor-notes/             开箱、版本更新、软件特性、SDK 说明
│  └─ operations/               目录映射、清理记录、上传范围、维护规则
├─ scripts/maintenance/         精确限定范围的整理工具
└─ .local-only/                 只留本机、Git 忽略
   ├─ vendor-sdk/               原厂整体 SDK/dl/sysroot，归档保留
   ├─ tools/windows/            flashing、drivers、industrial、communication、diagnostics
   ├─ metadata/nested-vendor-git/  原嵌套 Git 元数据备份
   └─ maintenance/              实际动作清单
```

源码输入只保存到正式来源目录，避免额外复制一套“最新源码”。
`SOURCE-INVENTORY.json` / `STAGES.json` / `SHA256SUMS` 是源码范围与版本的依据。
正式 `release-*` 包及已有阶段清单不改名、不改内部结构。
原厂七个编号顶层目录已撤除；文件版本名、CAD 配套关系和源码包内结构保持不变。
实际参与复现的厂商工具链/源包已归到 `software/`，prepare 脚本识别新旧工具链路径，
并校验同一个固定哈希。原厂 SDK 的三个大包继续保留在 `.local-only/vendor-sdk/`。
详细文件/目录映射见 [本地重构方案](local-reorganization-plan.json)，本机实际逐文件哈希
和动作清单在 `.local-only/maintenance/local-reorganization-20260928.json`。
旧的固定复现提交 `2e6074a` 保留原布局；无需修改历史提交或重新生成源码归档。

## openEuler 服务器

宿主机：`10.100.60.226`。开发容器：`dev_openeuler`。
容器目录 `/home/openeuler/build/` 对应宿主机卷：

```text
/home/docker_space/docker/volumes/dev_openeuler_vol-openeuler-build/_data/
```

新的分类入口在容器 `/home/openeuler/build/projects/`：

```text
projects/
├─ tl3572/
│  ├─ current -> ../../tl3572-2oo3
│  ├─ reproduction/20260928/     独立验证目录与源码克隆
│  │  ├─ github/                 repo、repo-v2、成功的 work-v3/work-v4
│  │  ├─ stage02-and-initial-m5/  Stage02 验证与首轮 M5 诊断
│  │  ├─ stage01-03-04-06-07/     其他阶段独立恢复/取源
│  │  ├─ stage05-final/          M5 最终全新目录重编
│  │  └─ layout-smoke-stage02/   本次整理后的新目录复现检查
│  ├─ exports/20260928/          最终共享输入、历史内核、全阶段归档
│  ├─ evidence/20260928/         成功日志和导出/验证驱动日志
│  ├─ archive/failed-runs/20260928/  失败运行日志及其来源清单
│  ├─ cache/20260928/verified-inputs/  有 SHA 校验的临时输入缓存
│  ├─ tools/20260928/            早期导出/构建辅助脚本
│  └─ maintenance/20260928/      删除对象、占用统计和操作记录
├─ rpi4/                        保留的树莓派入口；原目录不移动
│  ├─ current -> ../../build-rpi4-mica-uniproton
│  ├─ uefi -> ../../edk2-rpi4-20260818
│  └─ release-20260814、release-20260818 -> 原发布材料
└─ shared/                      共用源码、下载、工具链、缓存、通用 MCS
```

RK3588 独立工程已按用户确认删除，不在此分类中；共享上游源码中的 RK3588 支持代码
属于完整固定提交，未作裁剪。

`tl3572-2oo3` 主工作区、源码、Yocto 层、配置和原构建绝对路径保持不动。
新分类下 `current` 是入口，不是另一份源码副本。归类移动的成功验证/导出目录在原位置
保留**相对符号链接**，同时兼容宿主机与开发容器；不能改成容器看不到的宿主机绝对链接。
活动工程根部历史 `.git` 链接原本已失效，本次未改动；查看仓库版本请进入独立源码克隆
`reproduction/20260928/github/repo-v2/` 或本地仓库，不在该活动工程根部执行 Git 拉取。
新分类目录的属主为 SDK 用户 UID/GID 1000，原有源码/归档的属主不做递归调整。

例如：

| 原容器路径 | 新的实际位置（相对 `/home/openeuler/build/`） |
|---|---|
| `tl3572-github-repro-20260928/` | `projects/tl3572/reproduction/20260928/github/` |
| `tl3572-all-stages-validation-m5-final-20260928/` | `projects/tl3572/reproduction/20260928/stage05-final/` |
| `tl3572-all-stages-snapshots-v2-20260928/` | `projects/tl3572/exports/20260928/all-stages/` |
| `tl3572-all-stages-history-v2-20260928/` | `projects/tl3572/exports/20260928/historical/` |
| `rk3572-input-export-20260928-v5/` | `projects/tl3572/exports/20260928/rk3572-inputs/` |
| `tl3572-all-stages-evidence-20260928/` | `projects/tl3572/evidence/20260928/` |

## 后续维护规则

- 活动工程、正式源码、固定工具链、阶段清单和唯一历史证据不自动清理。
- 验证运行用新日期目录、新容器；不要复用失败工作区或原项目缓存。
- 同一阶段的源码版本由提交/哈希固定；目录改动不替代版本管理。
- 失败运行至少保留总日志和输入清单；不完整归档、重复展开树和失败临时库可删除。
- 共用 `src/downloads/sstate-cache/toolchains` 不根据芯片名批量删除。
- 删除先核对完整路径、依赖、Git worktree 注册和活动进程。禁止全局 Docker prune。
- 不在运行期间修改维护或构建脚本；本次维护脚本默认只预览，`-Apply` / `--apply` 才执行。
- Windows 安装包优先回收站；Linux 已确认删除的独立 RK3588 工程无恢复保证。
- 本地清单、密码、Token、私钥和 core 不上传。

服务器清理与初次本地归档见 [初次整理记录](cleanup-20260928.md)；
本地完整分类和售后/宣传清除见 [本地结构重构记录](local-reorganization-20260928.md)。
