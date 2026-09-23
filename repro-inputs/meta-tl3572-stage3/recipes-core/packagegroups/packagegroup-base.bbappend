# Same rationale as packagegroup-network.bbappend: with the nfs distro
# feature enabled, packagegroup-base hard-requires packagegroup-base-nfs,
# whose rpcbind/nfs-utils payload is unusable on the vendor 6.12 kernel.
RDEPENDS:packagegroup-base:remove = "packagegroup-base-nfs"
