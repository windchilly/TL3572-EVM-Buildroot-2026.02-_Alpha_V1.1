# Milestone 1 keeps the vendor TL3572 boot.img.  Do not pull the generic
# openEuler kernel into the board root filesystem.  This override is removed
# when linux-tl3572 becomes the reproducible virtual/kernel provider.
RDEPENDS:packagegroup-core-boot:remove:tl3572-evm = " \
    kernel \
    kernel-img \
    kernel-image \
    kernel-vmlinux \
"

