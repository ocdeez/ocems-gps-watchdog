import os
import time
import requests
from datetime import datetime, timezone, timedelta

# ==========================
# Load environment variables
# ==========================
ORG_ID = os.getenv("IC_ORG_ID")
CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")

GPS_STALE_MIN = int(os.getenv("GPS_STALE_THRESHOLD_MINUTES", 15))
REBOOT_COOLDOWN_MIN = int(os.getenv("REBOOT_COOLDOWN_MINUTES", 30))

# Load all devices dynamically
DEVICES = []
for i in range(1, 20):
    serial = os.getenv(f"IC_DEVICE{i}_SERIAL")
    name = os.getenv(f"IC_DEVICE{i}_NAME")
    if serial and name:
        DEVICES.append({"serial": serial, "name": name})

# Track reboot cooldowns
last_reboot = {}

# ==========================
# 1. Get OAuth Access Token
# ==========================
def get_access_token():
    token_url = f"https://api.ic.peplink.com/oauth2/token"
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()

    return resp.json()["access_token"]

# ==========================
# 2. Pull GPS from Peplink API
# ==========================
def get_gps(serial, token):
    # FIXED ENDPOINT
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/devices/{serial}/gps"

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        print("❌ GPS endpoint not found for device.")
        return None

    resp.raise_for_status()
    return resp.json()

# ==========================
# 3. Reboot Device
# ==========================
def reboot_device(serial, name, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/devices/{serial}/reboot"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"⚠️ Sending reboot command to {name} ({serial})...")
    resp = requests.post(url, headers=headers)
    resp.raise_for_status()

    last_reboot[serial] = datetime.now(timezone.utc)
    print("✔️ Reboot command issued.")

# ==========================
# 4. Check GPS staleness
# ==========================
def is_gps_stale(gps_obj):
    if gps_obj is None:
        return True

    # FIXED: Peplink wraps timestamp inside gps_info
    gps_info = gps_obj.get("gps_info")
    if not gps_info:
        return True

    ts = gps_info.get("timestamp")
    if not ts:
        return True

    try:
        gps_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return True

    age_seconds = (datetime.now(timezone.utc) - gps_time).total_seconds()

    print(f"   → GPS age: {int(age_seconds)} seconds")

    return age_seconds > GPS_STALE_MIN * 60

# ==========================
# 5. Main Loop
# ==========================
def main():
    print("🚑 OCEMS GPS Monitor Started")
    print(f"Monitoring {len(DEVICES)} devices")
    print("======================================")

    while True:
        try:
            token = get_access_token()

            for d in DEVICES:
                serial = d["serial"]
                name = d["name"]

                print(f"\n🔍 Checking {name} ({serial})...")

                gps_data = get_gps(serial, token)

                stale = is_gps_stale(gps_data)

                if not stale:
                    print("✔ GPS OK")
                    continue

                print("❗ GPS STALE — REBOOT REQUIRED")

                # Cooldown check
                last = last_reboot.get(serial)
                if last:
                    diff = datetime.now(timezone.utc) - last
                    if diff < timedelta(minutes=REBOOT_COOLDOWN_MIN):
                        print("⏳ Reboot SKIPPED — cooldown active")
                        continue

                reboot_device(serial, name, token)

        except Exception as e:
            print(f"🔥 ERROR: {e}")

        print("\n⏱ Sleeping 5 minutes...\n")
        time.sleep(300)


if __name__ == "__main__":
    main()
