# ytmusic-dl

> [!WARNING]  
> **Disclaimer:** This tool was created heavily using AI to save time. It was originally built just for my personal use, but I decided to open-source it. Use at your own discretion!

A zero-BS, interactive tool for ripping YouTube Music playlists and albums with proper metadata, square album art, and perfectly-synced lyrics.

### Usage
```bash
python3 ytmusic-dl.py [URL]
```
The script will interactively ask you for your preferred format (opus, mp3, flac, etc), output location, and if you want to embed synced lyrics.

#### Library Sync Mode
```bash
python3 ytmusic-dl.py --sync
```
When you download albums, a tiny `.ytmusic-dl.json` state file is generated inside the directory. If you ever lose connection, close the terminal, or encounter 403 Forbidden errors midway through downloading a discography, simply run `--sync`.
The script will recursively scan your entire working directory for these tracker files, automatically CD into those specific folders, and execute a surgical `yt-dlp` update pass to securely resume downloading any missing or corrupted tracks using your saved format settings! 

### Requirements
- Python 3.7+
- `yt-dlp` and `ffmpeg` in your PATH.
- *(Optional)* `mutagen` via pip for embedding lyrics directly into audio tags.

### Features
- Native support for **opus**, **mp3**, **m4a**, **flac**, and **wav**.
- Perfect metadata tagging (track numbers, artists, synced `.lrc` lyrics from LRCLIB).
- **Interactive Search:** Press `/` while selecting discography albums to instantly filter via a live search bar.
- Auto-crops YouTube thumbnails into perfectly square album covers.
- **50K-Scale Durability:** Multi-threaded fragment downloading, resilient file descriptor management, global SIGINT zombie-process tracking, and end-of-batch failed-download summaries.
- A beautiful, premium UI featuring macOS-style loading progress bars and fully fractional dynamic percentage readouts.

### License
[GPL-3.0](LICENSE)

