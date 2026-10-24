#!/bin/bash
# Fair FIFO slots for the shared machine. Up to $(cat slot.max) runs at once (default 2; Luke 2026-10-23:
# "Run more than one test at a time but ... throttle down" if the laptop slows). The first in the queue always
# runs; runs 2..N start only while the Mac is not under load (1-min load < 0.75*cores and no memory pressure).
# Set slot.max to 1 to go back to one at a time.
#   slot.sh acquire <name>   -> blocks until it's your turn AND the machine is free
#   slot.sh release <name>   -> frees your place (always call it, even on failure)
#   slot.sh show             -> prints the queue
# The queue file holds "name pid epoch" lines; entries whose pid has died are dropped.
# Run tests between acquire and release in the SAME shell, e.g.:
#   K="$HOME/Desktop/Alto Development/_qa/kit"; "$K/slot.sh" acquire me && { pytest ...; "$K/slot.sh" release me; }
K="$(cd "$(dirname "$0")" && pwd)"; Q="$K/slot.queue"; L="$K/slot.lockdir"
lock(){ until mkdir "$L" 2>/dev/null; do sleep 0.2; done; }
unlock(){ rmdir "$L" 2>/dev/null; }
overloaded(){ local c l p; c=$(sysctl -n hw.ncpu); l=$(sysctl -n vm.loadavg | awk '{print $2}'); p=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null || echo 1)
  awk -v l="$l" -v c="$c" 'BEGIN{exit !(l > 0.75*c)}' && return 0; [ "$p" -ge 2 ] && return 0; return 1; }
prune(){ [ -f "$Q" ] || return; : > "$Q.tmp"; while read -r n p t; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && echo "$n $p $t" >> "$Q.tmp"; done < "$Q"; mv "$Q.tmp" "$Q"; }
case "$1" in
  acquire)
    me="${2:-anon}"; owner=$PPID
    lock; prune; grep -q "^$me $owner " "$Q" 2>/dev/null || echo "$me $owner $(date +%s)" >> "$Q"; unlock
    while :; do
      lock; prune; pos=$(grep -n "^$me $owner " "$Q" 2>/dev/null | head -1 | cut -d: -f1); unlock
      max=$(cat "$K/slot.max" 2>/dev/null || echo 2)
      if [ "$pos" = 1 ]; then exit 0; fi
      if [ -n "$pos" ] && [ "$pos" -le "$max" ] && ! overloaded; then exit 0; fi
      sleep 15
    done ;;
  release)
    me="${2:-anon}"; lock; [ -f "$Q" ] && grep -v "^$me " "$Q" > "$Q.tmp"; [ -f "$Q.tmp" ] && mv "$Q.tmp" "$Q"; unlock ;;
  show) lock; prune; cat "$Q" 2>/dev/null; unlock ;;
  *) echo "usage: slot.sh acquire|release <name> | show"; exit 2 ;;
esac
