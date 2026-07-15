import sys
from pathlib import Path

# Mock process_lyrics
info_json_path = Path("/home/debarkak/Music/ytmusic-dl/Windows 96/Glass Prism/01 - I Swear.info.json")
lrc_path = info_json_path.with_suffix("").with_suffix(".lrc")

print("lrc_path:", lrc_path)
print("lrc exists before:", lrc_path.exists())

lyrics_mode = "embed"
embedded = True

if lyrics_mode == "embed" and embedded:
    try:
        lrc_path.unlink()
        print("unlink called!")
    except OSError as e:
        print("unlink failed:", e)

print("lrc exists after:", lrc_path.exists())
