import mutagen
from mutagen.id3 import ID3, USLT, SYLT, Encoding
try:
    audio = ID3("NA - Drive Slow.mp3")
    audio.add(USLT(encoding=Encoding.UTF8, lang='eng', desc='', text="test lyrics"))
    audio.save()
    print("MP3 embedded successfully")
except Exception as e:
    print(f"Error: {e}")
