# The TL3572 rootfs runs no NFS services and the vendor 6.12 kernel provides
# no nfsd filesystem, so the static proc-fs-nfsd.mount unit shipped with
# nfs-utils always fails at boot.  packagegroup-network-nfs is a hard
# RDEPENDS of packagegroup-network, so NO_RECOMMENDATIONS cannot keep it
# out of the image.  Drop the whole nfs subgroup for this layer's builds.
RDEPENDS:${PN}:remove = "packagegroup-network-nfs"
