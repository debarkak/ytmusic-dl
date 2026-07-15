import urllib.request
import re
import json

url = "https://music.youtube.com/channel/UCqilNN9HycR5kc1I1aAmJBg"
html = urllib.request.urlopen(urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
})).read().decode('utf-8')

api_key_match = re.search(r'"INNERTUBE_API_KEY":"(.*?)"', html)
client_version_match = re.search(r'"clientVersion":"(.*?)"', html)
client_name_match = re.search(r'"clientName":"(.*?)"', html)

if not api_key_match or not client_version_match:
    print("Failed to get API key")
    exit(1)

api_key = api_key_match.group(1)
client_version = client_version_match.group(1)
client_name = client_name_match.group(1)

print("API Key:", api_key)
print("Client Version:", client_version)
print("Client Name:", client_name)

# Make API call for See All
api_url = f"https://music.youtube.com/youtubei/v1/browse?key={api_key}"
payload = {
    "context": {
        "client": {
            "clientName": "WEB_REMIX", # YouTube Music
            "clientVersion": client_version
        }
    },
    "browseId": "MPADUCqilNN9HycR5kc1I1aAmJBg",
    "params": "ggMIegYIARoCAQI%3D"
}

req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json"
})
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode('utf-8'))
    
    def find_items(obj):
        if isinstance(obj, dict):
            if "musicTwoRowItemRenderer" in obj:
                yield obj["musicTwoRowItemRenderer"]
            for v in obj.values():
                yield from find_items(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from find_items(v)
                
    items = list(find_items(data))
    print(f"Found {len(items)} items on See All page")
    for item in items[:5]:
        title = item.get("title", {}).get("runs", [{}])[0].get("text", "Unknown")
        print(" -", title)
except Exception as e:
    print("API Error:", e)

