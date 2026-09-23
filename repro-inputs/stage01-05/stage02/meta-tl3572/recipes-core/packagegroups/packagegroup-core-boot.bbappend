# The vendor boot.img remains authoritative in stage 2.  Do not install the
# qemu-aarch64 5.10 kernel or its files into the TL3572 root filesystem.
RDEPENDS:${PN}:remove = "kernel kernel-img kernel-image kernel-vmlinux"
