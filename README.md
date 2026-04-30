# ytmusic-dl
a vibe coded downloader tool that downloads youtube music playlists/albums

### how to use

```bash
# clone it
git clone https://github.com/debarkak/ytmusic-dl.git
cd ytmusic-dl

# make it executable
chmod +x ytmusic-dl.sh

# run it
./ytmusic-dl.sh
```

the script will walk you through everything interactively — paste the url, pick a format, choose where to save, and it handles the rest

you can also skip the url prompt by passing it as an argument:

```bash
./ytmusic-dl.sh "https://music.youtube.com/playlist?list=OLAK5uy_..."
```

### features

- converts to any format supported by yt-dlp (opus, m4a, mp3, flac, wav)
- automatically embeds metadata (title, artist, album, etc.)
- embeds album art / thumbnails, auto-cropped to square so they don't look weird
- mp3 gets special treatment — VBR quality 0 (best) and jpg thumbnails for proper ID3 tag compat
- maps playlist index to track numbers so your files sort correctly
- organizes tracks into album folders with proper numbering (`01 - Song Name.opus`)
- concurrent fragment downloading (4 by default, tweak `FRAGMENTS` in the script if you want)
- won't re-download stuff you already have
- colored terminal output because we're not savages
- exits cleanly on errors or ctrl+c (resets terminal colors too)

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

### format options

| # | format | notes |
|---|--------|-------|
| 1 | opus   | native yt audio, no re-encoding (just use this) |
| 2 | m4a    | AAC, decent compat |
| 3 | mp3    | works on everything, tiny quality hit |
| 4 | flac   | lossless wrapper around a lossy source lol |
| 5 | wav    | uncompressed, will eat your storage |

defaults to opus if you just hit enter or type something weird

### output modes

| # | mode | what it does |
|---|------|--------------|
| 1 | flat | dumps everything in the current directory |
| 2 | album folder | creates a folder named after the album/playlist (recommended) |

defaults to album folder

### what's next

still working on the bash version, gonna add more features and improvements to it first before anything else. once it's solid enough i'll port it to python so it works on windows and other platforms too

### license

[GPL-3.0](LICENSE)
