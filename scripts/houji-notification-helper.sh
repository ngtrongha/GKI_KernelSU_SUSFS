#!/system/bin/sh
# Xiaomi 14 (houji) Background Notification & Greezer Exemption Helper
# Place in /data/adb/service.d/houji-notification-helper.sh or run via KSU boot-completed.sh

# Wait for Android boot completion
while [ "$(getprop sys.boot_completed)" != "1" ]; do
  sleep 2
done

# 1. Disable Xiaomi Greezer explicit 10s screen-off GMS freeze limiter
dumpsys greezer IM GMS disable >/dev/null 2>&1 || true

# 2. Ensure com.google.android.gms is in MILLET_NO_RESTRICT_APP to keep FCM TCP 5228 alive
CUR_LIST=$(settings --user 0 get system MILLET_NO_RESTRICT_APP 2>/dev/null)
case "$CUR_LIST" in
  *com.google.android.gms*) ;;
  null|"") settings --user 0 put system MILLET_NO_RESTRICT_APP "com.google.android.gms" ;;
  *) settings --user 0 put system MILLET_NO_RESTRICT_APP "${CUR_LIST},com.google.android.gms" ;;
esac

# 3. Disable Android 14/15/16 Phantom Process Killer & expand background app retention
device_config put activity_manager max_phantom_processes 2147483647 >/dev/null 2>&1 || true
