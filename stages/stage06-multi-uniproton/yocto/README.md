# Yocto 文件映射

目标层：`/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3`

| 归档文件 | 目标位置 |
|---|---|
| `linux-tl3572_6.12.69.bb` | `recipes-kernel/linux/linux-tl3572_6.12.69.bb` |
| `defconfig` | `recipes-kernel/linux/files/defconfig` |
| `../source/patches/kernel/*.patch` | `recipes-kernel/linux/files/` |
| `../source/mcs-km/mcs_km.c` | `recipes-kernel/linux/files/mcs_km.c` |
| `mcs-linux.bbappend` | `recipes-mcs/mcs-linux/mcs-linux.bbappend` |
| `../source/patches/mcs/*.patch` | `recipes-mcs/mcs-linux/files/` |
| `tl3572-openeuler-mcs-image.bb` | `recipes-core/images/tl3572-openeuler-mcs-image.bb` |
| `config/*.conf` | `recipes-core/images/files/` |
| `../firmware/rk3572-uniproton-up-*.elf` | `recipes-core/images/files/` |
| `services/*` | `recipes-core/images/files/` |

Stage04 已固定的 vendor kernel tarball、`localversion`、vendor boot、FIT its、DT overlay
和 mcs-km Makefile 继续沿用，不在本阶段重复归档。同步后运行
`../build/rebuild-m6-dual-image.sh`；脚本会 clean 内核和 MCS，再构建完整镜像。
