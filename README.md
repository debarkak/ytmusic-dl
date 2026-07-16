# ytmusic-dl

> [!WARNING]
> **disclaimer:** this tool was built heavily using ai to save time. it started as something i made for myself, but i eventually decided to open-source it. ai helped write a lot of the code, but everything has been tested, tweaked and broken enough times that i'm comfortable putting it out here.

a simple tool for downloading music from youtube music with proper metadata, square album art and synced lyrics.

### usage

```bash
python3 ytmusic-dl.py [url]
```

run it and it'll ask what format you want, where to save everything and whether to embed synced lyrics.

#### sync

```bash
python3 ytmusic-dl.py --sync
```

if a download fails or you stop it halfway through, run this. it'll scan for `.ytmusic-dl.json` files and resume whatever was left.

#### organize

```bash
python3 ytmusic-dl.py --organize
```

if your library ends up full of comma-separated artist names, this cleans them up automatically.

### requirements

- python 3.7+
- `yt-dlp` and `ffmpeg`
- *(optional)* `mutagen` for embedding lyrics into supported formats

### features

- downloads tracks, albums, playlists and artist discographies
- opus, mp3, m4a, flac and wav output
- proper metadata and synced `.lrc` lyrics
- press `/` to search while selecting albums
- automatically crops thumbnails into square album art
- resumes interrupted downloads with `--sync`
- clean progress bars with eta

### license

[gpl-3.0](LICENSE)