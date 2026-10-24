#!/bin/sh
# Stop the dashboard and bring the normal Kindle UI back.
if [ -f /tmp/dash/loop.pid ]; then
    kill "$(cat /tmp/dash/loop.pid)" 2>/dev/null
    rm -f /tmp/dash/loop.pid
fi
/etc/init.d/powerd start    > /dev/null 2>&1
/etc/init.d/framework start > /dev/null 2>&1
echo "dashboard stopped"
