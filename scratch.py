from pathlib import Path
info = Path("/home/debarkak/Music/ytmusic-dl/Windows 96/Glass Prism/01 - I Swear.info.json")
lrc = info.with_suffix("").with_suffix(".lrc")
print(lrc)
print(lrc.exists())
