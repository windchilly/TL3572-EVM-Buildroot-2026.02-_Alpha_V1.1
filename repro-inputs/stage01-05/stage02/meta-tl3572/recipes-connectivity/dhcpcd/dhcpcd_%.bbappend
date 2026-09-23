# systemd-networkd is the sole TL3572 network manager.  Keep the dhcpcd
# package available for now because the base package graph may require it,
# but never enable its system service in the image.
SYSTEMD_AUTO_ENABLE:${PN} = "disable"
