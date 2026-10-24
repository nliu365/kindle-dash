#!/bin/sh
# Turn the Kindle into the dashboard. The normal reading UI is stopped so it
# can't draw over the screen or put the device to sleep. Run stop.sh (or
# restart the Kindle) to get your Kindle back.
DIR=/mnt/us/dashboard

if [ ! -f "$DIR/config.sh" ]; then
    echo "Missing $DIR/config.sh - copy config.example.sh to config.sh and set BASE" >&2
    eips 2 18 "Missing dashboard/config.sh" > /dev/null 2>&1
    exit 1
fi

if [ -f /tmp/dash/loop.pid ] && kill -0 "$(cat /tmp/dash/loop.pid)" 2>/dev/null; then
    echo "dashboard already running"
    exit 0
fi

eips -c > /dev/null 2>&1
eips 10 18 "Starting dashboard..." > /dev/null 2>&1

/etc/init.d/framework stop > /dev/null 2>&1   # reading UI
/etc/init.d/powerd stop    > /dev/null 2>&1   # sleep / screensaver

# This firmware has no nohup; loop.sh ignores SIGHUP itself, and setsid
# (when present) detaches it from the SSH session entirely.
if command -v setsid > /dev/null 2>&1; then
    setsid sh "$DIR/loop.sh" < /dev/null > /dev/null 2>&1 &
else
    sh "$DIR/loop.sh" < /dev/null > /dev/null 2>&1 &
fi
sleep 2
if [ -f /tmp/dash/loop.pid ] && kill -0 "$(cat /tmp/dash/loop.pid)" 2>/dev/null; then
    echo "dashboard started (pid $(cat /tmp/dash/loop.pid))"
else
    echo "loop failed to start - run: sh $DIR/loop.sh   to see the error" >&2
    exit 1
fi
