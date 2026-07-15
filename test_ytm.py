import urllib.request
import re
import json
import codecs

url = "https://music.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}
req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req).read().decode('utf-8')

for match in re.finditer(r"initialData\.push\({path:\s*'\\/browse'.*?data:\s*'(.*?)'}\)", html):
    raw_data = match.group(1)
    # the data is encoded with \x sequences, let's decode it
    decoded_data = codecs.decode(raw_data.encode('utf-8'), 'unicode_escape')
    data = json.loads(decoded_data)
    
    def find_shelves(obj):
        if isinstance(obj, dict):
            if "musicCarouselShelfRenderer" in obj:
                yield obj["musicCarouselShelfRenderer"]
            for v in obj.values():
                yield from find_shelves(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from find_shelves(v)

    shelves = list(find_shelves(data))
    for shelf in shelves:
        header = shelf.get("header", {}).get("musicCarouselShelfBasicHeaderRenderer", {}).get("title", {}).get("runs", [{}])[0].get("text", "Unknown")
        print(f"Shelf: {header}")
        for item in shelf.get("contents", []):
            renderer = item.get("musicTwoRowItemRenderer")
            if renderer:
                title = renderer.get("title", {}).get("runs", [{}])[0].get("text", "Unknown")
                browse_id = renderer.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "Unknown")
                print(f"  - {title} (https://music.youtube.com/playlist?list={browse_id})")
