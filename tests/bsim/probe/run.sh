#!/bin/bash
# Run the radio probe (tx + rx on one phy) with 3 WLAN actmod interferers on Wi-Fi 1/6/11.
# usage: run.sh <ConfigSet|none>   needs BSIM_OUT_PATH and bs_probe_{tx,rx} in $BSIM_OUT_PATH/bin
# Geometry = ADR-0003 via multiatt path losses: pack (+20 dBm EIRP, emulated as 0 dBm radio + 40.2 dB) 10 m from rx,
# interferers (+20 dBm) 2 m from rx (free space 2.44 GHz: 46.2 dB).
set -e
cfg=${1:-none}
cd "$BSIM_OUT_PATH/bin"
sim=probe_${cfg}_$$
m=$(mktemp)
printf '0 1 : 40.2\n2 1 : 46.2\n3 1 : 46.2\n4 1 : 46.2\n' >"$m"
nw=3
[ "$cfg" = none ] && nw=0
./bs_2G4_phy_v1 -s="$sim" -D=$((2 + nw)) -sim_length=15100000 -channel=multiatt -defmodem=BLE_simple \
	-argschannel -file="$m" >/dev/null &
./bs_probe_tx -s="$sim" -d=0 | sed "s/^/cfg=$cfg /" &
./bs_probe_rx -s="$sim" -d=1 | sed "s/^/cfg=$cfg /" &
if [ $nw -gt 0 ]; then
	i=2
	for ch in 1 6 11; do
		./bs_device_2G4_WLAN_actmod -s="$sim" -d=$i -channel=$ch -ConfigSet="$cfg" -power=20 >/dev/null &
		i=$((i + 1))
	done
fi
wait
rm -f "$m"
