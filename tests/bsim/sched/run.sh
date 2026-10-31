#!/bin/bash
# #22 / AIR-4: run one pack (fw, sysbuild, both cores) alone on the phy, then check its on-air schedule
# from the phy's Tx dump. usage: run.sh <path to fw zephyr.exe> [sim seconds, default 1]
# needs BSIM_OUT_PATH (logs and the phy dump land in $BSIM_OUT_PATH/results/sched_<pid>).
# Every process runs under timeout with -sim_length (hands-off.md, CI discipline).
exe=$(realpath "$1")
secs=${2:-1}
here=$(dirname "$(realpath "$0")")
mkdir -p "$BSIM_OUT_PATH/results"
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=sched_$$
pids=()
trap 'kill "${pids[@]}" 2>/dev/null' EXIT
timeout 120 ./bs_2G4_phy_v1 -s="$sim" -D=1 -sim_length=$((secs * 1000000 + 20000)) >"/dev/null" 2>&1 &
pids+=($!)
timeout 120 "$exe" -s="$sim" -d=0 >"$BSIM_OUT_PATH/results/$sim.pack.log" 2>&1 &
pids+=($!)
wait "${pids[@]}"
grep -E "OpenPack|SCHED" "$BSIM_OUT_PATH/results/$sim.pack.log"
python3 "$here/check.py" "$BSIM_OUT_PATH/results/$sim/d_2G4_00.Tx.csv"
