#!/bin/sh
# Main loop that runs on the Kindle 4 (BusyBox shell). Started by start.sh.
trap '' HUP          # keep running after the SSH session that started us closes
DIR=/mnt/us/dashboard
. "$DIR/config.sh"
TMP=/tmp/dash
mkdir -p "$TMP"
echo $$ > "$TMP/loop.pid"

log() { echo "$(date '+%F %T') $*" >> "$TMP/dash.log"; }

# --- Press any button to go back to reader mode -----------------------------
# One blocking dd per input device (keypad, 5-way, side keys). Whichever gets an
# event first drops a flag file; the loop checks it every second.
arm_buttons() {
    rm -f "$TMP/pressed" "$TMP/watch.pids"
    for ev in /dev/input/event*; do
        [ -c "$ev" ] || continue
        ( dd if="$ev" of=/dev/null bs=16 count=1 2>/dev/null; touch "$TMP/pressed" ) &
        echo $! >> "$TMP/watch.pids"
    done
}

exit_to_reader() {
    log "button pressed - returning to reader mode"
    rm -f "$TMP/loop.pid"                  # so stop.sh doesn't kill this process
    exec sh "$DIR/stop.sh" button
}

nap() {  # sleep N seconds, but react to a button press within ~1 s
    n=$1
    while [ "$n" -gt 0 ]; do
        [ -f "$TMP/pressed" ] && exit_to_reader
        sleep 1
        n=$((n - 1))
    done
}

# BusyBox 1.7 wget has no timeout option, so a watchdog kills a stalled download.
dl() {  # dl URL OUTFILE SECONDS
    wget -q -O "$2" "$1" &
    wpid=$!
    ( sleep "$3"; kill "$wpid" 2>/dev/null ) &
    dogpid=$!
    wait "$wpid"
    rc=$?
    kill "$dogpid" 2>/dev/null
    return $rc
}

fetch() {  # fetch NAME -> $TMP/NAME, only replaces the old copy on success
    rm -f "$TMP/$1.part"
    if dl "$BASE/$1" "$TMP/$1.part" 30 && [ -s "$TMP/$1.part" ]; then
        mv "$TMP/$1.part" "$TMP/$1"
        return 0
    fi
    log "fetch $1 failed"
    return 1
}

show() { eips -f -g "$1" > /dev/null 2>&1; }   # -f = full flashing refresh, clears ghosting

wifi_up() { lipc-set-prop com.lab126.wifid enable 1 > /dev/null 2>&1; }

battery_note() {
    pct=$(gasgauge-info -c 2>/dev/null | tr -dc '0-9')
    if [ -n "$pct" ] && [ "$pct" -lt 15 ]; then
        eips 1 38 "Battery ${pct}% - please plug in" > /dev/null 2>&1
    fi
}

minutes=$REFRESH_MIN    # force a refresh on the first pass
fails=0
wifi_up
sleep 3                 # let any key press that launched us settle
arm_buttons

while true; do
    # 1) Refresh the dashboard image
    if [ "$minutes" -ge "$REFRESH_MIN" ]; then
        if fetch dash.png; then
            fetch alarm.png
            show "$TMP/dash.png"
            battery_note
            minutes=0
            fails=0
        else
            fails=$((fails + 1))
            [ "$fails" -eq 3 ] && eips 1 38 "No connection - retrying" > /dev/null 2>&1
            wifi_up
        fi
    fi

    # 2) Ask the server whether an alarm is ringing right now
    rm -f "$TMP/status"
    dl "$BASE/status" "$TMP/status" 15
    status=$(cat "$TMP/status" 2>/dev/null)
    case "$status" in
        ALARM*)
            log "alarm: $status"
            # flash for ~55 s, then re-check (server keeps ALARM for ALARM_MINUTES)
            i=0
            while [ $i -lt 11 ]; do
                [ -f "$TMP/alarm.png" ] && show "$TMP/alarm.png" || eips -c > /dev/null 2>&1
                nap 2
                [ -f "$TMP/dash.png" ] && show "$TMP/dash.png"
                nap 3
                i=$((i + 1))
            done
            ;;
        *)
            nap 60
            ;;
    esac
    minutes=$((minutes + 1))
done
