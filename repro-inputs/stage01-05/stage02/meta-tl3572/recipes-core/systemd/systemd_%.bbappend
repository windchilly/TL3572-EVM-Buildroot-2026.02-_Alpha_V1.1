# systemd-networkd stores DHCP DNS data in systemd-resolved.  Build the
# resolver so /etc/resolv.conf is usable on the target without dhclient races.
PACKAGECONFIG:append = " resolved"
