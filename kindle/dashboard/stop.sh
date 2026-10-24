#!/bin/sh
# Stop the dashboard and bring the normal Kindle UI back.
# Called by hand over SSH, or by loop.sh when a button is pressed.
TMP=/tmp/dash
if [ -f "$TMP/loop.pid" ]; then
    kill "$(cat "$TMP/loop.pid")" 2>/dev/null
    rm -f "$TMP/loop.pid"
fi
# stop the button watchers (subshells, then the dd processes they started)
if [ -f "$TMP/watch.pids" ]; then
    for p in $(cat "$TMP/watch.pids"); do kill "$p" 2>/dev/null; done
    rm -f "$TMP/watch.pids"
fi
killall dd > /dev/null 2>&1
rm -f "$TMP/pressed"

eips -c > /dev/null 2>&1
eips 10 18 "Returning to Kindle..." > /dev/null 2>&1
/etc/init.d/powerd start    > /dev/null 2>&1
/etc/init.d/framework start > /dev/null 2>&1
echo "dashboard stopped"
