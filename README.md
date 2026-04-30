# ytmusic-dl
a vibe coded downloader tool that downloads youtube music playlists/albums

### how it works

open up the script, paste the url of the youtube music playlist/album, choose what format you want to use, folder directory, and the script will rip everything off the playlist/album

### features

- converts to any format supported by yt-dlp (opus, m4a, mp3, flac, wav)
- automatically cleans up the file names and metadata
- embeds album art / thumbnails (auto-cropped to square)
- organizes tracks into album folders with proper numbering
- concurrent fragment downloading for speed
- won't re-download stuff you already have (`--no-overwrites`)
- colored terminal output because we're not savages

### dependencies

you need these installed before running:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/)

the script will yell at you if they're missing, but here's how to install them anyway:

```bash
# arch
sudo pacman -S yt-dlp ffmpeg

# debian/ubuntu
sudo apt install yt-dlp ffmpeg

# mac
brew install yt-dlp ffmpeg
```

### usage

```bash
# clone it
git clone https://github.com/debarkak/ytmusic-dl.git
cd ytmusic-dl

# make it executable
chmod +x ytmusic-dl.sh

# run it
./ytmusic-dl.sh
```

you can also pass the url directly as an argument if you don't wanna go through the prompt:

```bash
./ytmusic-dl.sh "https://music.youtube.com/playlist?list=OLAK5uy_..."
```

### format options

| # | format | notes |
|---|--------|-------|
| 1 | opus   | native yt audio, no re-encoding (just use this) |
| 2 | m4a    | AAC, decent compat |
| 3 | mp3    | works on everything, tiny quality hit |
| 4 | flac   | lossless wrapper around a lossy source lol |
| 5 | wav    | uncompressed, will eat your storage |

### output modes

- **flat** — dumps everything in the current directory
- **album folder** — creates a folder named after the album/playlist and puts tracks in there (recommended)

tracks are named like `01 - Track Name.ext` so they sort properly

### license

[GPL-3.0](LICENSE)
