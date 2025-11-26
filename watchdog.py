import os, time, requests, datetime, pytz

CLIENT_ID = os.getenv("IC_CLIENT_ID")
CLIENT_SECRET = os.getenv("IC_CLIENT_SECRET")
USERNAME = os.getenv("IC_USERNAME")
PASSWORD = os.getenv("IC_PASSWORD")
ORG_ID = os.getenv("IC_ORG_ID")
DEVICE_SERIAL = os.getenv("IC_DEVICE_SERIAL")
STALE_THRESHOLD_MINUTES = int(os.getenv("STALE_THRESHOLD", "15"))

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}", flush=True)

def get_token():
    url = "https://api.ic.peplink.com/api/oauth2/token"
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def get_gps(token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{DEVICE_SERIAL}/gps_info"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def reboot_device(token):
    url = f"https://api.ic.peplink.com/rest/o/{ORG_ID}/d/{DEVICE_SERIAL}/reboot"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(url, headers=headers)
    r.raise_for_status()
    log("⚠️  Device reboot command issued!")

def main():
    while True:
        try:
            token = get_token()
            gps = get_gps(token)
            last_update = gps.get("time")
            log(f"Last GPS update: {last_update}")

            if last_update:
                utc = pytz.UTC
                gps_time = utc.localize(datetime.datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%S%z"))
                now = datetime.datetime.now(pytz.UTC)
                diff = (now - gps_time).total_seconds() / 60
                if diff > STALE_THRESHOLD_MINUTES:
                    log(f"GPS stale ({diff:.1f} min old) → rebooting")
                    reboot_device(token)
                else:
                    log(f"GPS healthy ({diff:.1f} min old)")
            else:
                log("No GPS timestamp → rebooting")
                reboot_device(token)

        except Exception as e:
            log(f"Error: {e}")

        time.sleep(600)   # wait 10 min before next check

if __name__ == "__main__":
    main()

