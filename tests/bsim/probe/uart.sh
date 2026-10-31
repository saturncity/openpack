#!/bin/bash
# UART -> pty probe: bs_probe_uart writes "PROBE_UART_OK n" to uart0; read_pty.py must see it on the host pty.
# needs BSIM_OUT_PATH and bs_probe_uart in $BSIM_OUT_PATH/bin. Hard-kills everything on exit: with
# -uart_pty_wait the device spins in nanosleep until a reader attaches and does not honour SIGTERM.
here=$(cd "$(dirname "$0")" && pwd)
cd "$BSIM_OUT_PATH/bin" || exit 1
sim=uart_$$
d=$(mktemp -d)
pids=()
trap 'kill -9 "${pids[@]}" 2>/dev/null; rm -rf "$d"' EXIT
timeout -s KILL 60 ./bs_2G4_phy_v1 -s="$sim" -D=1 -sim_length=4000000 >"$d/phy.log" 2>&1 &
pids+=($!)
timeout -s KILL 60 ./bs_probe_uart -s="$sim" -d=0 -uart0_pty -uart_pty_wait >"$d/dev.log" 2>&1 &
pids+=($!)
python3 "$here/read_pty.py" "$d/dev.log" PROBE_UART_OK
rc=$?
[ $rc -ne 0 ] && { echo "--- dev.log"; head -5 "$d/dev.log"; }
echo "uart probe rc=$rc"
exit $rc
