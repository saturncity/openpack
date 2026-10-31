#!/bin/bash
# Run the radio probe (tx + rx on one phy) with 3 WLAN actmod interferers on Wi-Fi 1/6/11.
# usage: run.sh <ConfigSet|none> [extra actmod args, e.g. -sigma=0.8 -power=15]
# needs BSIM_OUT_PATH and bs_probe_{tx,rx} in $BSIM_OUT_PATH/bin
# Geometry = ADR-0003 via multiatt path losses: pack (+20 dBm EIRP, emulated as 0 dBm radio + 40.2 dB) 10 m from rx,
# interferers 2 m from rx (free space 2.44 GHz: 46.2 dB). Interferer power defaults to 20 dBm (actmod default).
# Every process runs under timeout with -sim_length; leftovers are killed on exit (hands-off.md, CI discipline).
cfg=${1:-none}
shift
extra=("$@")
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=probe_${cfg}_$$
d=$(mktemp -d)
pids=()
trap 'kill "${pids[@]}" 2>/dev/null; rm -rf "$d"' EXIT
printf '0 1 : 40.2\n2 1 : 46.2\n3 1 : 46.2\n4 1 : 46.2\n' >"$d/m"
nw=3
[ "$cfg" = none ] && nw=0
T=120
names=(phy tx rx)
timeout $T ./bs_2G4_phy_v1 -s="$sim" -D=$((2 + nw)) -sim_length=15100000 -channel=multiatt -defmodem=BLE_simple \
	-argschannel -file="$d/m" >"$d/phy.log" 2>&1 &
pids+=($!)
timeout $T ./bs_probe_tx -s="$sim" -d=0 >"$d/tx.log" 2>&1 &
pids+=($!)
timeout $T ./bs_probe_rx -s="$sim" -d=1 >"$d/rx.log" 2>&1 &
pids+=($!)
ch=(0 1 6 11)
for i in $(seq 1 $nw); do
	timeout $T ./bs_device_2G4_WLAN_actmod -s="$sim" -d=$((i + 1)) -channel=${ch[$i]} -ConfigSet="$cfg" -power=20 \
		"${extra[@]}" >"$d/w$i.log" 2>&1 &
	pids+=($!)
	names+=(wlan$i)
done
rc=0
for i in "${!pids[@]}"; do
	wait "${pids[$i]}"
	e=$?
	[ $e -ne 0 ] && rc=1
	echo "cfg=$cfg ${names[$i]} exit=$e"
done
tag="cfg=$cfg${extra[*]:+ ${extra[*]}}"
grep -h PROBE_RESULT "$d/rx.log" | sed -E "s/^.*PROBE_RESULT/$tag/" |
	awk '{for(i=1;i<=NF;i++){split($i,a,"=");v[a[1]]=a[2]} printf "%s loss=%.3f\n",$0,1-v["ok"]/v["n"]}'
grep -q PROBE_DONE "$d/rx.log" || { echo "$tag rx did not finish"; rc=1; }
[ $rc -ne 0 ] && for f in "$d"/*.log; do echo "--- $(basename "$f") tail"; tail -n 4 "$f" | cut -c1-200; done
exit $rc
