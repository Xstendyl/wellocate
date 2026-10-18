#!/bin/sh
# LAUNCH A LONG JOB AND RECORD ITS PID, so it can be stopped by PID and never by a name pattern.
#
# WHY. `pkill -f "deepseek-chat-v3.1"` once killed a live top-up run because the pattern matched its own
# command line. On 2026-09-29 `pkill -f verify_citations` killed four waiting shells for the same reason,
# minutes after the lesson was restated. A pattern matches whatever it matches. A PID does not.
#
#   scripts/runjob.sh <name> <command...>      launch, writing results/pids/<name>.pid
#   scripts/runjob.sh --stop <name>            stop that job, by PID, and only that job
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/results/pids"
if [ "$1" = "--stop" ]; then
    f="$root/results/pids/$2.pid"
    [ -f "$f" ] || { echo "no pid file for $2"; exit 1; }
    pid=$(cat "$f")
    if kill -0 "$pid" 2>/dev/null; then kill "$pid" && echo "stopped $2 (pid $pid)"; else echo "$2 (pid $pid) is not running"; fi
    rm -f "$f"
    exit 0
fi
name=$1; shift
"$@" &
echo $! > "$root/results/pids/$name.pid"
echo "launched $name as pid $(cat "$root/results/pids/$name.pid")"
