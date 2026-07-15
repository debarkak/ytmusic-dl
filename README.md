# ytmusic-dl

An interactive tool for downloading YouTube Music playlists and albums.

## Requirements

Ensure the following are installed and in your system PATH:
- **Python 3.7+**
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**
- **[ffmpeg](https://ffmpeg.org/)**

## Usage

Clone the repository and run the script:

```bash
git clone https://github.com/debarkak/ytmusic-dl.git
cd ytmusic-dl

python3 ytmusic-dl.py
```

The script will interactively prompt you for the URL, format (e.g., opus, mp3), and output location.

To skip the URL prompt, pass it as an argument:
```bash
python3 ytmusic-dl.py "<YTMUSIC_URL>"
```

## Features

- Supports `opus`, `mp3`, `m4a`, `flac`, and `wav`.
- Automatically embeds metadata and square-cropped album art.
- Organizes files into album folders with proper track numbering.
- Skips already downloaded tracks.
- Concurrent downloads for speed.

## License

[GPL-3.0](LICENSE)
