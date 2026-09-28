# Keep the M6 layer unchanged and use the same M7 patch as the standalone build.
FILESEXTRAPATHS:prepend := "${THISDIR}/../../../../patches/mcs:"
SRC_URI += "file://0003-rpc-shared-log-lifecycle.patch"
