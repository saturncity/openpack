#!/bin/bash
# #97 / ADR-0022: the pack's frame lead loop on bsim. One pack (fw, sysbuild, both cores) alone on the
# phy (-nodump: an hour of Tx dumps would be gigabytes), its audio frame clock offset by a test-only
# rate (-op_fclk_ppb, src/app/bsim_fclk.c), then check_lead.py on the pack log: 0 skips, 0 repeats,
# the lead held. "open" leaves the loop open: the negative control, which must slip.
# usage: lead.sh <path to fw zephyr.exe> <sim seconds> <fclk ppb> [open]
# needs BSIM_OUT_PATH (logs land in $BSIM_OUT_PATH/results/lead_<pid>.pack.log).
# Every process runs under timeout with -sim_length (hands-off.md, CI discipline).
exe=$(realpath "$1")
secs=$2
ppb=$3
open=${4:-}
here=$(dirname "$(realpath "$0")")
mkdir -p "$BSIM_OUT_PATH/results"
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=lead_$$
log=$BSIM_OUT_PATH/results/$sim.pack.log
wall=$((secs + 300))
args=(-s="$sim" -d=0 -op_fclk_ppb="$ppb")
[ "$open" = open ] && args+=(-op_lead_open)
pids=()
trap 'kill "${pids[@]}" 2>/dev/null' EXIT
timeout $wall ./bs_2G4_phy_v1 -s="$sim" -D=1 -nodump -sim_length=$((secs * 1000000 + 20000)) >/dev/null 2>&1 &
pids+=($!)
OP_AUDIO_IN=/dev/null timeout $wall "$exe" "${args[@]}" >"$log" 2>&1 &
pids+=($!)
wait "${pids[@]}"
grep -E "SCHED start|PACK audio" "$log"
python3 "$here/check_lead.py" "$log" "$secs" "$ppb" ${open:+--open}
