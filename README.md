# ytmusic-dl
A zero-BS, interactive tool for ripping YouTube Music playlists and albums with proper metadata, square album art, and perfectly-synced lyrics.

### Usage
```bash
python3 ytmusic-dl.py [URL]
```
The script will interactively ask you for your preferred format (opus, mp3, flac, etc), output location, and if you want to embed synced lyrics.

### Requirements
- Python 3.7+
- `yt-dlp` and `ffmpeg` in your PATH.
- *(Optional)* `mutagen` via pip for embedding lyrics directly into audio tags.

### Features
- Native support for **opus**, **mp3**, **m4a**, **flac**, and **wav**.
- Perfect metadata tagging (track numbers, artists, synced `.lrc` lyrics from LRCLIB).
- Auto-crops YouTube thumbnails into perfectly square album covers.
- Multi-threaded fragment downloading.

### License
[GPL-3.0](LICENSE)
