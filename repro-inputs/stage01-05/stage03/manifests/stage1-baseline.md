# TL3572 openEuler 阶段1构建基线清单

验证时间：2026-09-15（Asia/Shanghai）  
验证目标：`10.100.60.226:2005` / `dev_openeuler`  
独立工作区：`/home/openeuler/build/tl3572-2oo3`

## 容器与资源

| 项目 | 固定值或实测值 |
|---|---|
| 容器系统 | openEuler 24.03 LTS-SP2，x86_64 |
| 容器ID | `6f47adafeaa381eacc2898bfcc2a8fb7828f162b6d8d08c9d356a96d212c18f7` |
| 容器镜像ID | `sha256:ed46fbc8a8ecb67c87b2fc46439aea1e50b4712d404ed4c00e57a471f505f887` |
| 容器镜像摘要 | `swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f` |
| CPU | 64个逻辑CPU |
| 内存 | 64 GB标称；容器实测总量61 GiB/61.9 GiB，可用约54 GiB |
| Swap | 31 GiB |
| Docker资源限制 | 未设置单独的memory/cpuset硬限制；容器共享宿主机资源上限 |
| 构建卷 | ext4，约1.7 TiB；验证时剩余578 GiB |

## 构建工具

| 项目 | 固定值 |
|---|---|
| oebuild | `0.2.1.2` |
| Python | `3.11.6` |
| Git | `2.43.0` |
| CMake | `3.27.9` |
| Ninja | `1.11.1` |
| BitBake | `2.0.0` |
| Native SDK | `/opt/buildtools/nativesdk` |
| AArch64工具链 | `/usr1/openeuler/gcc/openeuler_gcc_arm64le` |
| GCC | `aarch64-openeuler-linux-gnu-gcc 12.3.1 20230508` |
| GCC可执行文件SHA256 | `0b2f6c2c7842e7839a233a8abda4f0ac4b92dcaa0580d6bacd90771c482a218a` |
| `.oebuild/config` SHA256 | `55c8b6b3b0334e701e40c756f5f83bda7c52a3f97c531dc917484d904f85dd4d` |

## 源码锁定

| 仓库 | 提交 |
|---|---|
| yocto-meta-openeuler | `3aa6999c9ab78569bc2209a9dbb185e2f7e4301c`（`openEuler-24.03-LTS`） |
| yocto-poky | `4bf0e3ea7a5cd4577ae43c510870f235a39eedc0`（清单版本`v4.0.10`） |
| yocto-meta-openembedded | `a82d92c8a6525da01524bf8f4a60bf6b35dcbb3d`（清单版本`dev_kirkstone`） |
| mcs | `5cb49156276be04d54a77a630b8600dcc122fdba` |
| UniProton | `1d102888822449b8205894db4f483abc71c0d05b` |
| OpenAMP | `5fbe563479c2c137a442659e87f603dd323a03c3` |
| libmetal | `69e96d9620652df428ec7f4faca92f70cce111d3` |

以上七个仓库在独立工作区中均为干净工作树。`mcs`、OpenAMP和libmetal提交取自openEuler 24.03 LTS清单；UniProton使用现有RK3588参考树对应的上游提交建立干净副本，参考树里的未提交修改未带入基线。

## 厂商内核基线

| 项目 | 固定值 |
|---|---|
| 源码包 | `linux-6.12.69-v1.0-gf1b67c2.tar.gz` |
| 文件大小 | `270376279` bytes |
| SHA256 | `186FACE3889200078EF67A8D97F1ED587E4E1D1E30683A81566D5E85A2D60608` |

## 验证结果

- SSH、源码读取和构建卷写入：通过。
- openEuler 24.03 LTS主仓及两个基础Yocto层独立拉取：通过。
- 七个源码仓提交与干净状态检查：通过。
- AArch64工具链链接测试：通过，产物为ELF64 little-endian AArch64 PIE。
- Native SDK、BitBake和oebuild可执行性：通过。
- 共享`downloads`与`sstate-cache`可读写：通过。
- 原有RK3588、MCS及UniProton参考工作树复核：状态未改变。
- QEMU构建或启动：未执行，符合阶段1范围。

阶段1结论：`COMPLETE`。
