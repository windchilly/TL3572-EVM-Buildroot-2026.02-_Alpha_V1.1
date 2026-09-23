FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += " \
    file://0001-mcs-rpmsg-tty-full-payload.patch \
    file://0002-baremetal-rproc-route-dual-sgi-events.patch \
"
