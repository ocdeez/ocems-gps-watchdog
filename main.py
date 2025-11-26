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

# Load all devices dynamically from environment
DEVICES = []
for i in range(1, 20):
    serial = os.getenv(f"IC_DEVICE{i}_SERIAL")
    name = os.getenv(f"IC_DEVICE{i}_NAME")
    if serial and name:
        DEVICES.append({"serial": serial, "name": name})

# Track cooldowns
last_reboot = {}

# ==========================
# 1. Get an access token
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
# 2. Query Device GPS Info
# ==========================
def get_gps(serial, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/gps"

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 404:
        return None  # Devices without GPS return "not found"

    resp.raise_for_status()
    return resp.json()

# ==========================
# 3. Reboot Device
# ==========================
def reboot_device(serial, name, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/reboot"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"⚠️ Rebooting {name} ({serial})...")
    resp = requests.post(url, headers=headers)
    resp.raise_for_status()

    last_reboot[serial] = datetime.now(timezone.utc)
    print(f"✔️ Reboot command sent successfully.")

# ==========================
# 4. Determine GPS staleness
# ==========================
def is_gps_stale(gps_obj):
    if gps_obj is None:
        return True

    if "timestamp" not in gps_obj:
        return True

    ts = gps_obj["timestamp"]  # Example: "2025-02-01T03:12:00Z"
    gps_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - gps_time

    return age.total_seconds() > (GPS_STALE_MIN * 60)

# ==========================
# 5. Main Loop
# ==========================
def main():
    print("🚑 OCEMS GPS Monitor Service Started")
    print(f"Monitoring {len(DEVICES)} devices...")
    print("----------------------------------------")

    while True:
        try:
            token = get_access_token()

            for d in DEVICES:
                serial = d["serial"]
                name = d["name"]

                print(f"\nChecking {name} ({serial})...")

                gps_data = get_gps(serial, token)

                if gps_data is None:
                    print("⚠️ No GPS data found — treating as stale.")
                    gps_stale = True
                else:
                    gps_stale = is_gps_stale(gps_data)

                if not gps_stale:
                    print("✔️ GPS OK")
                    continue

                print("❗ GPS STALE — needs reboot.")

                # Check cooldown
                last = last_reboot.get(serial)
                if last:
                    diff = datetime.now(timezone.utc) - last
                    if diff < timedelta(minutes=REBOOT_COOLDOWN_MIN):
                        print("⏳ Reboot skipped — cooldown active.")
                        continue

                reboot_device(serial, name, token)

        except Exception as e:
            print(f"🔥 ERROR: {e}")

        print("\nSleeping 5 minutes...\n")
        time.sleep(300)


if __name__ == "__main__":
    main()
