#!/bin/sh
# One-time setup (run on the Kindle over SSH):
#   sh /mnt/us/dashboard/install-autostart.sh
# Afterwards: Menu > Settings > Menu > Restart boots into the dashboard,
# and pressing any button returns to reader mode.
# Turn off:  rm /mnt/us/dashboard/AUTOSTART     (Kindle then boots normally)
# Remove:    sh /mnt/us/dashboard/install-autostart.sh uninstall
set -e
DIR=/mnt/us/dashboard
if [ "$1" = "uninstall" ]; then
    mntroot rw
    rm -f /etc/rc5.d/S99dashboard /etc/init.d/dashboard
    mntroot ro
    rm -f "$DIR/AUTOSTART"
    echo "autostart removed"
    exit 0
fi
[ -f "$DIR/config.sh" ] || { echo "missing $DIR/config.sh" >&2; exit 1; }
mntroot rw
cp "$DIR/boot.sh" /etc/init.d/dashboard
chmod 755 /etc/init.d/dashboard
ln -sf ../init.d/dashboard /etc/rc5.d/S99dashboard
mntroot ro
touch "$DIR/AUTOSTART"
ls -l /etc/rc5.d/S99dashboard
echo "autostart installed: restart the Kindle to boot into the dashboard"
