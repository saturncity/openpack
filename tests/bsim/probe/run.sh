#!/bin/bash
# Run the radio probe (tx + rx on one phy) with 3 WLAN actmod interferers on Wi-Fi 1/6/11.
# usage: run.sh <ConfigSet|none>   needs BSIM_OUT_PATH and bs_probe_{tx,rx} in $BSIM_OUT_PATH/bin
# Geometry = ADR-0003 via multiatt path losses: pack (+20 dBm EIRP, emulated as 0 dBm radio + 40.2 dB) 10 m from rx,
# interferers (+20 dBm) 2 m from rx (free space 2.44 GHz: 46.2 dB).
cfg=${1:-none}
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=probe_${cfg}_$$
d=$(mktemp -d)
printf '0 1 : 40.2\n2 1 : 46.2\n3 1 : 46.2\n4 1 : 46.2\n' >"$d/m"
nw=3
[ "$cfg" = none ] && nw=0
names=(phy tx rx)
./bs_2G4_phy_v1 -s="$sim" -D=$((2 + nw)) -sim_length=15100000 -channel=multiatt -defmodem=BLE_simple \
	-argschannel -file="$d/m" >"$d/phy.log" 2>&1 &
pids=($!)
./bs_probe_tx -s="$sim" -d=0 >"$d/tx.log" 2>&1 &
pids+=($!)
./bs_probe_rx -s="$sim" -d=1 >"$d/rx.log" 2>&1 &
pids+=($!)
ch=(0 1 6 11)
for i in $(seq 1 $nw); do
	./bs_device_2G4_WLAN_actmod -s="$sim" -d=$((i + 1)) -channel=${ch[$i]} -ConfigSet="$cfg" -power=20 >"$d/w$i.log" 2>&1 &
	pids+=($!)
	names+=(wlan$i)
done
for i in "${!pids[@]}"; do
	wait "${pids[$i]}"
	echo "cfg=$cfg ${names[$i]} exit=$?"
done
grep -h PROBE "$d/tx.log" "$d/rx.log" | sed "s/^/cfg=$cfg /"
for f in "$d"/*.log; do echo "--- $(basename "$f") tail"; tail -n 4 "$f" | cut -c1-200; done
rm -rf "$d"
