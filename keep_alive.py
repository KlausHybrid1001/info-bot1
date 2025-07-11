import requests
import time

# URL of your server's keep-alive endpoint
url = "https://info-bot1-1.onrender.com/keepalive"

# Interval in seconds (e.g., every 10 minutes)
interval = 300

while True:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("Keep-alive request successful")
        else:
            print(f"Keep-alive request failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending keep-alive request: {e}")
    
    # Wait for the specified interval before sending the next request
    time.sleep(interval)
