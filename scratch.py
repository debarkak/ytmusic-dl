from mutagen.id3 import ID3
audio = ID3("/home/debarkak/Music/ytmusic-dl/Windows 96/Glass Prism/01 - I Swear.mp3")
for frame in audio.values():
    print(f"{frame.FrameID}: {repr(frame)}")
