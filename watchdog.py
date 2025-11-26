import os, time, requests, datetime

CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")
ORG_ID = os.getenv("IC_ORG_ID")
GROUP_ID = os.getenv("IC_GROUP_ID")
DEVICE_SERIALS = [x.strip() for x in os.getenv("IC_DEVICE_SERIALS", "").split(",")]
STALE_THRESHOLD_MINUTES = int(os.getenv("STALE_THRESHOLD", "15"))

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}", flush=True)

def get_token():
    url = "https://api.ic.peplink.com/api/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def get_gps(token, serial):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/gps_info"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def reboot_device(token, serial):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{serial}/reboot"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(url, headers=headers)
    r.raise_for_status()
    log(f"⚠️ REBOOT SENT to {serial}")

def main():
    while True:
        try:
            token = get_token()
            now = datetime.datetime.utcnow()

            for serial in DEVICE_SERIALS:
                try:
                    gps = get_gps(token, serial)
                    last_update = gps.get("time")

                    if not last_update:
                        log(f"{serial}: NO GPS REPORTED → rebooting")
                        reboot_device(token, serial)
                        continue

                    gps_time = datetime.datetime.fromisoformat(last_update.replace("Z","+00:00"))
                    diff = (now - gps_time).total_seconds() / 60

                    if diff > STALE_THRESHOLD_MINUTES:
                        log(f"{serial}: STALE GPS ({diff:.1f} min old) → rebooting")
                        reboot_device(token, serial)
                    else:
                        log(f"{serial}: GPS OK ({diff:.1f} min old)")

                except Exception as e:
                    log(f"{serial}: ERROR → {e}")

        except Exception as e:
            log(f"GLOBAL ERROR → {e}")

        time.sleep(600)  # check every 10 minutes

if __name__ == "__main__":
    main()
