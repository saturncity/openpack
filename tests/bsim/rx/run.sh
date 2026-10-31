#!/bin/bash
# #23 / RX-2..RX-4, RX-10: one pack + one receiver (fw, sysbuild, both cores each) on one phy, clean channel.
# usage: run.sh <pack zephyr.exe> <rx zephyr.exe> <a|e>
#   (e) needs a pack built with -Dfw_net_CONFIG_OP_PACK_TEST_RUN_MS=3000 (goes silent after 3 s)
#   a: pack and receiver power on together, 10 s. Asserts lock <= 2 s, then 0 lost frames, 0 seq skips.
#   e: pack reboots twice: pack #1 runs 0-3 s, pack #2 (fresh boot, other frame phase) 3.0503-6.0503 s,
#      pack #3 from 7.0007 s, 10 s total. Power-off = OP_PACK_TEST_RUN_MS (the device stays on the
#      phy, silent); power-on = a new device process with -start_offset (fresh boot, new phase). Asserts re-lock <= 2 s after each boot, 0 loss while locked.
# Crystals at the AIR-4 / RX-7 limits: pack +20 ppm, receiver -20 ppm, so tracking (RX-3) must follow.
# needs BSIM_OUT_PATH (logs in $BSIM_OUT_PATH/results/rx_<scenario>_<pid>.*).
# Every process runs under timeout with -sim_length (hands-off.md, CI discipline).
pack=$(realpath "$1")
rx=$(realpath "$2")
sc=${3:-a}
here=$(dirname "$(realpath "$0")")
mkdir -p "$BSIM_OUT_PATH/results"
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=rx_${sc}_$$
log=$BSIM_OUT_PATH/results/$sim
secs=10
pids=()
trap 'kill "${pids[@]}" 2>/dev/null' EXIT
P="-xo_drift=20e-6"
if [ "$sc" = a ]; then
	nd=2
	packs=("-d=0 $P")
	starts="0"
	stops="$secs"
else
	nd=4
	packs=("-d=0 $P" "-d=2 $P -start_offset=3050300" "-d=3 $P -start_offset=7000700")
	starts="0,3.0503,7.0007"
	stops="3,6.0503,$secs"
fi
timeout 300 ./bs_2G4_phy_v1 -s="$sim" -D=$nd -sim_length=$((secs * 1000000)) >"$log.phy.log" 2>&1 &
pids+=($!)
timeout 300 "$rx" -s="$sim" -d=1 -xo_drift=-20e-6 >"$log.rx.log" 2>&1 &
pids+=($!)
for i in "${!packs[@]}"; do
	# shellcheck disable=SC2086 # word splitting of the per-pack args is intended
	timeout 300 "$pack" -s="$sim" ${packs[$i]} >"$log.pack$i.log" 2>&1 &
	pids+=($!)
done
wait "${pids[@]}"
grep -hE "RX (start|lock|reacquire)|pipeline" "$log.rx.log"
python3 "$here/check.py" "$log.rx.log" "$starts" "$stops"
