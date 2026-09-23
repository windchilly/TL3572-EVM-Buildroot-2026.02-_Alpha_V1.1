# UniProton RK3572 M5 源码覆盖包说明

## 基线与文件

- 上游仓库：`https://gitee.com/openeuler/UniProton.git`
- 基线提交：`1d102888822449b8205894db4f483abc71c0d05b`
- 覆盖包：`../source/overlay/uniproton-rk3572-m5-source-overlay.tar.gz`
- SHA256：`a55ca4fa6706e1d7746780a045ebf1f7d9207a93ed8b0e40b15dd31f59eeaae3`

该包保存 M5 最终构建所需的全部已修改文件和 RK3572 新增源码，共 49 个条目；
不含 `build/` 下的 CMake 中间文件、构建生成的 `libs/`，也不含构建脚本会重新
下载的 libmetal/OpenAMP 解包目录。它是对指定基线的“最终文件覆盖包”，不是
可用于其他 UniProton 版本的通用补丁。

## 恢复与构建

在干净的基线源码顶层执行：

```sh
git checkout 1d102888822449b8205894db4f483abc71c0d05b
tar -xzf /path/to/uniproton-rk3572-m5-source-overlay.tar.gz
cd demos/rk3572_mica/build
./build_app.sh
```

脚本已加入 fail-fast：静态库、libmetal/OpenAMP 或应用任一步失败都会返回非零，
不会继续复制旧 ELF。成功产物位于：

```text
demos/rk3572_mica/build/rk3572_mica.elf
```

当前构建脚本使用：

```text
/home/openeuler/build/tl3572-2oo3/toolchain-14.3
```

工具链目录需要提供 `aarch64-none-elf-*` 到
`aarch64-none-linux-gnu-*` 的兼容软链接，并在 GCC 14.3 的规格目录提供
空的 `nosys.specs`；这是现有 demo 构建参数的兼容要求。

最终 ELF 位于 `../firmware/rk3572-uniproton-final.elf`，校验值：

```text
大小：589064 bytes
入口：0x7c200000
SHA256：3faa550c98c18a407e1a2816b3c022c82fc91d85b3fb968b83ffed32631478d0
```

入口及其 LOAD 段必须位于 `mcs-rmem@7a000000` 的 64 MiB 范围内；
CPU7 的 OpenAMP 池为 `0x7a0e0000..0x7a0fffff`，固件从
`0x7c200000` 起，二者不得重叠。
