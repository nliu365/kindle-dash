#!/bin/sh
# Main loop that runs on the Kindle 4 (BusyBox shell). Started by start.sh.
DIR=/mnt/us/dashboard
. "$DIR/config.sh"
TMP=/tmp/dash
mkdir -p "$TMP"
echo $$ > "$TMP/loop.pid"

log() { echo "$(date '+%F %T') $*" >> "$TMP/dash.log"; }

fetch() {  # fetch NAME -> $TMP/NAME, only replaces the old copy on success
    rm -f "$TMP/$1.part"
    if wget -q -T 20 -O "$TMP/$1.part" "$BASE/$1" && [ -s "$TMP/$1.part" ]; then
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
    status=$(wget -q -T 15 -O - "$BASE/status" 2>/dev/null)
    case "$status" in
        ALARM*)
            log "alarm: $status"
            # flash for ~55 s, then re-check (server keeps ALARM for ALARM_MINUTES)
            i=0
            while [ $i -lt 11 ]; do
                [ -f "$TMP/alarm.png" ] && show "$TMP/alarm.png" || eips -c > /dev/null 2>&1
                sleep 2
                [ -f "$TMP/dash.png" ] && show "$TMP/dash.png"
                sleep 3
                i=$((i + 1))
            done
            ;;
        *)
            sleep 60
            ;;
    esac
    minutes=$((minutes + 1))
done
