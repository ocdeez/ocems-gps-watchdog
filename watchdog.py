import os
import time
import requests
from datetime import datetime, timezone, timedelta

ORG_ID = os.getenv("IC_ORG_ID")
CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

GPS_STALE_MIN = int(os.getenv("GPS_STALE_THRESHOLD_MINUTES", 15))
REBOOT_COOLDOWN_MIN = int(os.getenv("REBOOT_COOLDOWN_MINUTES", 30))

# Load all devices
DEVICES = []
for i in range(1, 20):
    serial = os.getenv(f"IC_DEVICE{i}_SERIAL")
    name = os.getenv(f"IC_DEVICE{i}_NAME")
    if serial and name:
        DEVICES.append({"serial": serial, "name": name})

last_reboot = {}
last_status = {}  # For "GPS recovered" alerts


# -----------------------------------
# Discord Alert Helper
# -----------------------------------
def send_discord(message: str):
    if not DISCORD_WEBHOOK:
        return
    
    payload = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass


# -----------------------------------
# Access Token
# -----------------------------------
def get_access_token():
    token_url = "https://api.ic.peplink.com/oauth2/token"

    resp = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


# -----------------------------------
# GPS Info
# -----------------------------------
def get_gps(serial, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/gps"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        return None  # Device may not report GPS

    resp.raise_for_status()
    return resp.json()


# -----------------------------------
# Reboot Device
# -----------------------------------
def reboot_device(serial, name, token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/reboot"
    headers = {"Authorization": f"Bearer {token}"}
    
    send_discord(f"🚨 **Rebooting {name}** (`{serial}`) — GPS stale too long.")

    resp = requests.post(url, headers=headers)
    resp.raise_for_status()

    last_reboot[serial] = datetime.now(timezone.utc)


# -----------------------------------
# GPS Stale Check
# -----------------------------------
def is_gps_stale(gps_obj):
    if gps_obj is None:
        return True

    ts = gps_obj.get("timestamp")
    if not ts:
        return True

    gps_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    age_minutes = (datetime.now(timezone.utc) - gps_time).total_seconds() / 60

    return age_minutes > GPS_STALE_MIN


# -----------------------------------
# Main Loop
# -----------------------------------
def main():
    send_discord("🚑 **OCEMS GPS Watchdog Started**")
    print("Watchdog started.")

    while True:
        try:
            token = get_access_token()

            for d in DEVICES:
                serial = d["serial"]
                name = d["name"]

                gps_data = get_gps(serial, token)
                stale = is_gps_stale(gps_data)

                # ------- GPS OK -------
                if not stale:
                    if last_status.get(serial) == "STALE":
                        send_discord(f"✅ **GPS Restored for {name}** (`{serial}`)")
                    last_status[serial] = "OK"
                    continue

                # ------- GPS STALE -------
                if last_status.get(serial) != "STALE":
                    send_discord(f"⚠️ **GPS Stale Detected** on {name} (`{serial}`)")
                    last_status[serial] = "STALE"

                # cooldown check
                last = last_reboot.get(serial)
                if last:
                    if datetime.now(timezone.utc) - last < timedelta(minutes=REBOOT_COOLDOWN_MIN):
                        send_discord(
                            f"⏳ **Cooldown active** — Skipping reboot for {name} (`{serial}`)."
                        )
                        continue

                reboot_device(serial, name, token)

        except Exception as e:
            send_discord(f"🔥 **Watchdog Error:** `{e}`")
            print("ERROR:", e)

        time.sleep(300)  # 5 minutes
