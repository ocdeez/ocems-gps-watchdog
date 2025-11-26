import os
import time
import requests
from datetime import datetime, timezone, timedelta

# ==========================================
# Load environment variables
# ==========================================
ORG_ID = os.getenv("IC_ORG_ID")  # MUST be full OrgID, not short code
CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")

GPS_STALE_MIN = int(os.getenv("GPS_STALE_THRESHOLD_MINUTES", 5))
REBOOT_COOLDOWN_MIN = int(os.getenv("REBOOT_COOLDOWN_MINUTES", 10))

# Load devices dynamically
DEVICES = []
for i in range(1, 20):
    serial = os.getenv(f"IC_DEVICE{i}_SERIAL")
    name = os.getenv(f"IC_DEVICE{i}_NAME")
    if serial and name:
        DEVICES.append({"serial": serial.strip(), "name": name.strip()})

# Track cooldowns
last_reboot = {}

# ==========================================
# 1. OAUTH TOKEN
# ==========================================
def get_access_token():
    url = "https://api.ic.peplink.com/oauth2/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    resp = requests.post(url, data=payload)
    resp.raise_for_status()

    return resp.json()["access_token"]


# ==========================================
# 2. GET GPS INFO
# ==========================================
def get_gps(serial, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/gps_info"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        return None

    resp.raise_for_status()
    return resp.json()


# ==========================================
# 3. SEND REBOOT COMMAND
# ==========================================
def reboot_device(serial, name, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/ctrl/reboot"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"⚠️  Rebooting {name} ({serial})...")
    resp = requests.post(url, headers=headers)

    if resp.status_code not in [200, 202, 204]:
        print(f"❌ Reboot failed: {resp.text}")
        resp.raise_for_status()

    last_reboot[serial] = datetime.now(timezone.utc)
    print("✔️  Reboot command sent.")


# ==========================================
# 4. GPS STALENESS CHECK
# ==========================================
def is_gps_stale(gps):
    if gps is None:
        return True

    ts = gps.get("timestamp")
    if not ts or ts == "" or ts == "0000-00-00T00:00:00Z":
        return True

    try:
        gps_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return True

    age = datetime.now(timezone.utc) - gps_time
    return age.total_seconds() > (GPS_STALE_MIN * 60)


# ==========================================
# 5. MAIN LOOP
# ==========================================
def main():
    print("🚑 OCEMS GPS Watchdog Started")
    print(f"Monitoring {len(DEVICES)} devices")

    while True:
        try:
            token = get_access_token()

            for d in DEVICES:
                serial = d["serial"]
                name = d["name"]

                print(f"\n--- Checking {name} ({serial}) ---")

                gps = get_gps(serial, token)

                if not is_gps_stale(gps):
                    print("✔ GPS OK")
                    continue

                print("❗ GPS stale — REBOOT REQUIRED")

                last = last_reboot.get(serial)
                if last:
                    if datetime.now(timezone.utc) - last < timedelta(minutes=REBOOT_COOLDOWN_MIN):
                        print("⏳ Cooldown active — skipping reboot")
                        continue

                reboot_device(serial, name, token)

        except Exception as e:
            print(f"🔥 ERROR: {e}")

        print("\nSleeping 5 minutes...\n")
        time.sleep(300)


if __name__ == "__main__":
    main()
