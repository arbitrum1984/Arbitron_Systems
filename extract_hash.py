import urllib.request
import json

req = urllib.request.Request(
    "https://api.github.com/repos/arbitrum1984/Arbitron_Systems/events",
    headers={'User-Agent': 'Mozilla/5.0'}
)
try:
    with urllib.request.urlopen(req) as response:
        events = json.loads(response.read().decode())
        found = False
        for event in events:
            if event['type'] == 'PushEvent':
                print(f"PushEvent at {event['created_at']}: before={event['payload'].get('before')}, head={event['payload'].get('head')}")
                found = True
        if not found:
            print("No PushEvents found.")
except Exception as e:
    print(f"Error: {e}")
