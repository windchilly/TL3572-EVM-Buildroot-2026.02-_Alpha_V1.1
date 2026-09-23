# Third nfs dependency path found by dnf --whatrequires on the image feed:
# packagegroup-core-full-cmdline-sys-services hard-requires nfs-utils and
# rpcbind.  The vendor 6.12 kernel has no nfsd filesystem and the TL3572
# runs no NFS services, so drop just these two from the subgroup.
RDEPENDS:packagegroup-core-full-cmdline-sys-services:remove = "nfs-utils rpcbind"
