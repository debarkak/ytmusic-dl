import urllib.request, urllib.parse, json

def search(artist, title):
    query = urllib.parse.quote(f"{artist} {title}")
    url = f"https://lrclib.net/api/search?q={query}"
    req = urllib.request.Request(url, headers={"User-Agent": "ytmusic-dl (https://github.com/debarkak/ytmusic-dl)"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data:
                return data[0].get("syncedLyrics") or data[0].get("plainLyrics")
    except Exception as e:
        print(f"Error: {e}")
    return None

print(search("Windows 96", "Drive Slow")[:50])
