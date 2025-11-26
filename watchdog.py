import os
import time
import requests
from datetime import datetime, timezone, timedelta

# ==================================================
# Load Environment Variables
# ==================================================
ORG_ID = os.getenv("IC_ORG_ID")
CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

GPS_STALE_MIN = int(os.getenv("GPS_STALE_THRESHOLD_MINUTES", 15))
REBOOT_COOLDOWN_MIN = int(os.getenv("REBOOT_COOLDOWN_MINUTES", 30))

# Load all devices dynamically
DEVICES = []
for i in range(1, 20):
    serial = os.getenv(f"IC_DEVICE{i}_SERIAL")
    name = os.getenv(f"IC_DEVICE{i}_NAME")
    if serial and name:
        DEVICES.append({"serial": serial, "name": name})

# Track cooldowns & previous states
last_reboot = {}
previous_gps_stale_state = {}

# ==================================================
# Discord Notification Function
# ==================================================
def notify(message: str):
    """Send message to Discord if webhook is configured."""
    if not DISCORD_WEBHOOK:
        print("⚠️ No Discord webhook configured.")
        return

    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print(f"🔥 Failed to send Discord alert: {e}")


# ==================================================
# 1. Get Access Token
# ==================================================
def get_access_token():
    token_url = "https://api.ic.peplink.com/oauth2/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()

    return resp.json()["access_token"]


# ==================================================
# 2. Query GPS
# ==================================================
def get_gps(serial, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/gps"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        return None  # Some devices return 404 if no GPS module

    resp.raise_for_status()
    return resp.json()


# ==================================================
# 3. Reboot Device
# ==================================================
def reboot_device(serial, name, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/reboot"
    headers = {"Authorization": f"Bearer {token}"}

    notify(f"🔄 Rebooting **{name}** (`{serial}`)…")

    resp = requests.post(url, headers=headers)
    resp.raise_for_status()

    last_reboot[serial] = datetime.now(timezone.utc)

    notify(f"✅ Reboot command sent successfully for **{name}** (`{serial}`).")


# ==================================================
# 4. Determine GPS staleness
# ==================================================
def is_gps_stale(gps_obj):
    if gps_obj is None:
        return True

    if "timestamp" not in gps_obj:
        return True

    gps_time = datetime.fromisoformat(gps_obj["timestamp"].replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - gps_time

    return age.total_seconds() > (GPS_STALE_MIN * 60)


# ==================================================
# 5. Main Loop
# ==================================================
def main():
    notify("🚑 **OCEMS GPS Watchdog Started** — service is now running.")
    print("🚑 OCEMS GPS Watchdog Started")

    while True:
        try:
            token = get_access_token()

            for d in DEVICES:
                serial = d["serial"]
                name = d["name"]

                print(f"\nChecking {name} ({serial})…")
                gps_data = get_gps(serial, token)

                gps_stale = is_gps_stale(gps_data)

                # Detect GPS recovery
                prev_state = previous_gps_stale_state.get(serial, None)
                if prev_state is True and gps_stale is False:
                    notify(f"🟢 **GPS Restored** for **{name}** (`{serial}`)")
                
                previous_gps_stale_state[serial] = gps_stale

                if not gps_stale:
                    print("✔️ GPS OK")
                    continue

                # GPS stale now
                notify(f"⚠️ **GPS Stale** detected for **{name}** (`{serial}`).")

                # Cooldown check
                last = last_reboot.get(serial)
                if last:
                    diff = datetime.now(timezone.utc) - last
                    if diff < timedelta(minutes=REBOOT_COOLDOWN_MIN):
                        notify(
                            f"⏳ Reboot skipped for **{name}** — cooldown "
                            f"({REBOOT_COOLDOWN_MIN} min) still active."
                        )
                        continue

                reboot_device(serial, name, token)

        except Exception as e:
            error_text = f"🔥 **ERROR:** {e}"
            print(error_text)
            notify(error_text)

        print("Sleeping 5 minutes…\n")
        time.sleep(300)


if __name__ == "__main__":
    main()
