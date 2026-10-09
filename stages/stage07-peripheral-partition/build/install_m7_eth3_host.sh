#!/usr/bin/env bash
# Run on the TL3572 board with the two source/host files staged in one directory.
set -euo pipefail
readonly source_dir=${1:?Usage: install_m7_eth3_host.sh DIRECTORY_WITH_SCRIPT_AND_SERVICE}
if [[ $(id -u) != 0 ]]; then echo "Board root required" >&2; exit 1; fi
for name in eth3_power_enable.py m7-eth3-power.service; do
    test -f "$source_dir/$name"
done
for destination in /usr/libexec/m7/eth3_power_enable.py /etc/systemd/system/m7-eth3-power.service; do
    name=$(basename "$destination")
    if [[ -e "$destination" ]] && ! cmp -s "$source_dir/$name" "$destination"; then
        echo "Refusing to overwrite a different existing file: $destination" >&2; exit 1
    fi
done
/usr/bin/python3 "$source_dir/eth3_power_enable.py"
if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$source_dir/m7-eth3-power.service"
else
    echo "systemd-analyze absent; verify loaded unit and actual oneshot execution below" >&2
fi
install -d /usr/libexec/m7
install -m 0644 "$source_dir/eth3_power_enable.py" /usr/libexec/m7/eth3_power_enable.py
install -m 0644 "$source_dir/m7-eth3-power.service" /etc/systemd/system/m7-eth3-power.service
systemctl daemon-reload
systemctl enable --now m7-eth3-power.service
systemctl show m7-eth3-power.service --property=LoadState,ActiveState,SubState,Result,ExecMainStatus
systemctl is-active m7-eth3-power.service
systemctl is-enabled m7-eth3-power.service
