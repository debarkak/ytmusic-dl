# ytmusic-dl

a vibe coded downloader tool that downloads youtube music playlists/albums

## how to use

```bash
# clone it
git clone https://github.com/debarkak/ytmusic-dl.git
cd ytmusic-dl

# run it (python 3)
python3 ytmusic-dl.py

# or the bash version if you prefer
chmod +x ytmusic-dl.sh
./ytmusic-dl.sh
```

the script will walk you through everything interactively — paste the url, pick a format, choose where to save, and it handles the rest

you can also skip the url prompt by passing it as an argument:

```bash
python3 ytmusic-dl.py "https://music.youtube.com/playlist?list=OLAK5uy_..."
```

## features

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
- works on linux, macos, and windows

## dependencies

you need these installed before running:

- [python 3](https://www.python.org/) (3.7+, no pip packages needed)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/)

the script will yell at you if they're missing, but here's how to install them anyway:

```bash
# arch
sudo pacman -S python yt-dlp ffmpeg

# debian/ubuntu
sudo apt install python3 yt-dlp ffmpeg

# mac
brew install python yt-dlp ffmpeg

# windows (with scoop)
scoop install python yt-dlp ffmpeg
```

## format options

| # | format | notes                                           |
|---|--------|-------------------------------------------------|
| 1 | opus   | native yt audio, no re-encoding (just use this) |
| 2 | m4a    | AAC, decent compat                              |
| 3 | mp3    | works on everything, tiny quality hit            |
| 4 | flac   | lossless wrapper around a lossy source lol       |
| 5 | wav    | uncompressed, will eat your storage              |

defaults to opus if you just hit enter or type something weird

## output modes

| # | mode         | what it does                                                  |
|---|--------------|---------------------------------------------------------------|
| 1 | flat         | dumps everything in the current directory                     |
| 2 | album folder | creates a folder named after the album/playlist (recommended) |

defaults to album folder

## license

[GPL-3.0](LICENSE)
