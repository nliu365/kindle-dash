#!/bin/sh
# Installed as /etc/init.d/dashboard and linked as /etc/rc5.d/S99dashboard
# by install-autostart.sh. Starts the dashboard at boot, but only when the
# switch file /mnt/us/dashboard/AUTOSTART exists.
case "$1" in
start)
    (
        # wait (up to ~3 min) for the user storage (/mnt/us) to be mounted
        i=0
        while [ ! -f /mnt/us/dashboard/start.sh ] && [ $i -lt 90 ]; do
            sleep 2; i=$((i + 1))
        done
        [ -f /mnt/us/dashboard/AUTOSTART ] || exit 0
        sleep 45            # let the reading UI and Wi-Fi finish starting
        sh /mnt/us/dashboard/start.sh > /dev/null 2>&1
    ) < /dev/null > /dev/null 2>&1 &
    ;;
stop|restart)
    ;;
esac
exit 0
