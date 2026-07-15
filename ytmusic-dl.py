#!/usr/bin/env python3
# ─────────────────────────────────────────────
#  ytmusic-dl.py
#  deps: yt-dlp, ffmpeg
# ─────────────────────────────────────────────

import sys
import re
import signal
import shutil
import subprocess
import time
import platform
import json
import codecs
import urllib.request
import urllib.parse
from pathlib import Path

try:
    import mutagen
    from mutagen.id3 import ID3, USLT, Encoding
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
except ImportError:
    mutagen = None


# ── platform detection ──────────────────────
IS_WINDOWS = platform.system() == "Windows"


# ── windows setup ───────────────────────────
def _init_windows():
    """enable ansi colors and utf-8 on windows"""
    if not IS_WINDOWS:
        return

    # enable VT100 escape sequences in windows terminal
    # this makes ansi color codes work in cmd.exe and powershell
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)

        # do the same for stderr
        handle_err = kernel32.GetStdHandle(-12)
        mode_err = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle_err, ctypes.byref(mode_err))
        kernel32.SetConsoleMode(handle_err, mode_err.value | 0x0004)
    except Exception:
        pass

    # set console output to utf-8 so box drawing chars work
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    # also set the python io encoding
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


_init_windows()


# ── colors ──────────────────────────────────
class C:
    """ansi color codes"""
    RED = "\033[0;31m"
    GRN = "\033[0;32m"
    YLW = "\033[1;33m"
    CYN = "\033[0;36m"
    MGN = "\033[0;35m"
    BLU = "\033[0;34m"
    BLD = "\033[1m"
    DIM = "\033[2m"
    RST = "\033[0m"


# disable colors if not a tty (piping, redirects, etc.)
if not sys.stdout.isatty():
    for attr in ("RED", "GRN", "YLW", "CYN", "MGN", "BLU", "BLD", "DIM", "RST"):
        setattr(C, attr, "")


# ── config ──────────────────────────────────
FRAGMENTS = 4

FORMAT_OPTIONS = {
    "1": ("opus", f"native yt audio, no re-encoding  {C.GRN}← recommended{C.RST}"),
    "2": ("m4a",  "AAC, decent compat"),
    "3": ("mp3",  "works on everything, tiny quality hit"),
    "4": ("flac", "lossless wrapper around a lossy source lol"),
    "5": ("wav",  "uncompressed, will eat your storage"),
}


# ── helpers ─────────────────────────────────
def hr(color=None):
    c = color or C.DIM
    print(f"{c}──────────────────────────────────────────{C.RST}")


def section(title):
    print()
    hr(C.CYN)
    print(f"  {C.CYN}{C.BLD}{title}{C.RST}")
    hr(C.CYN)
    print()


def reset_colors():
    print(C.RST, end="", flush=True)


# ── signal handling ─────────────────────────
def handle_interrupt(sig, frame):
    print(f"\n{C.RST}{C.RED}{C.BLD}  ✗ interrupted{C.RST}")
    sys.exit(130)


signal.signal(signal.SIGINT, handle_interrupt)

# SIGTERM doesn't exist on windows
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, handle_interrupt)


# ── dependency check ────────────────────────
def check_deps():
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")

    if missing:
        print(f"  {C.RED}✗{C.RST} missing deps: {C.BLD}{' '.join(missing)}{C.RST}")
        if IS_WINDOWS:
            print(f"    {C.DIM}install them with scoop/choco/winget{C.RST}")
        else:
            print(f"    {C.DIM}just install them (pacman/apt/brew idc){C.RST}")
        sys.exit(1)

    try:
        ytdlp_ver = subprocess.check_output(
            ["yt-dlp", "--version"],
            stderr=subprocess.DEVNULL,
            text=True,
            # hide the console window on windows
            **(_subprocess_kwargs()),
        ).strip()
    except Exception:
        ytdlp_ver = "?"

    print(f"  {C.GRN}✓{C.RST} {C.DIM}yt-dlp {ytdlp_ver} · ffmpeg found{C.RST}")


def _subprocess_kwargs():
    """extra kwargs for subprocess calls on windows to suppress console popups"""
    if IS_WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return {"startupinfo": si}
    return {}


# ── banner ──────────────────────────────────
def banner():
    print()
    print(f"{C.MGN}  ╔══════════════════════════════════════╗{C.RST}")
    print(f"{C.MGN}  ║                                      ║{C.RST}")
    print(f"{C.MGN}  ║{C.RST}   {C.BLD}♫  ytmusic-dl{C.RST}                      {C.MGN}║{C.RST}")
    print(f"{C.MGN}  ║{C.RST}   {C.DIM}rip anything off yt music{C.RST}          {C.MGN}║{C.RST}")
    print(f"{C.MGN}  ║                                      ║{C.RST}")
    print(f"{C.MGN}  ╚══════════════════════════════════════╝{C.RST}")
    print()


# ── validate URL ────────────────────────────
def validate_url(url):
    pattern = r"^https?://(www\.)?(music\.)?youtube\.com/|^https?://youtu\.be/"
    if not re.match(pattern, url):
        print(f"  {C.YLW}!{C.RST} {C.DIM}that doesn't look like a youtube url, trying anyway...{C.RST}")


# ── prompt URL ──────────────────────────────
def prompt_url(arg_url=None):
    if arg_url:
        print(f"  {C.GRN}✓{C.RST} {C.BLD}url{C.RST} {C.DIM}(from arg){C.RST}")
        print(f"    {C.CYN}{arg_url}{C.RST}")
        validate_url(arg_url)
        return arg_url

    print(f"  {C.BLD}drop the url:{C.RST}")
    try:
        url = input("    → ").strip()
    except EOFError:
        url = ""

    if not url:
        print(f"  {C.RED}✗{C.RST} bro u didn't paste anything")
        sys.exit(1)

    validate_url(url)
    print(f"  {C.GRN}✓{C.RST} {C.BLD}url{C.RST}")
    return url


# ── prompt format ───────────────────────────
def prompt_format():
    print()
    print(f"  {C.BLD}what format?{C.RST}")
    print()
    for key, (fmt, desc) in FORMAT_OPTIONS.items():
        print(f"    {C.YLW}{key}{C.RST})  {fmt:<6} {C.DIM}─{C.RST} {desc}")
    print()

    try:
        choice = input("    [1-5, default 1]: ").strip()
    except EOFError:
        choice = ""

    if not choice:
        choice = "1"

    if choice in FORMAT_OPTIONS:
        audio_format = FORMAT_OPTIONS[choice][0]
    else:
        print(f"    {C.YLW}!{C.RST} {C.DIM}not valid, defaulting to opus{C.RST}")
        audio_format = "opus"

    print(f"  {C.GRN}✓{C.RST} {C.BLD}{audio_format}{C.RST}")
    return audio_format


# ── prompt directory ────────────────────────
def prompt_directory():
    print()
    print(f"  {C.BLD}where to save?{C.RST}")
    print()
    print(f"    {C.YLW}1{C.RST})  right here {C.DIM}─{C.RST} no folder, just dumps the files")
    print(f"    {C.YLW}2{C.RST})  album folder {C.DIM}─{C.RST} named after the album/thing  {C.GRN}← recommended{C.RST}")
    print(f"    {C.YLW}3{C.RST})  artist folder {C.DIM}─{C.RST} Artist / Album / Song")
    print()

    try:
        choice = input("    [1-3, default 2]: ").strip()
    except EOFError:
        choice = ""

    if not choice:
        choice = "2"

    # yt-dlp handles path separators internally, so / works on all platforms
    if choice == "1":
        template = "%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "flat"
    elif choice == "2":
        template = "%(album,playlist_title,title)s/%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "album_folder"
    elif choice == "3":
        template = "%(artist,uploader)s/%(album,playlist_title,title)s/%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "artist_folder"
    else:
        print(f"    {C.YLW}!{C.RST} {C.DIM}not valid, going with album folder{C.RST}")
        template = "%(album,playlist_title,title)s/%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "album_folder"

    print(f"  {C.GRN}✓{C.RST} {C.BLD}{mode}{C.RST}")
    return template, mode


# ── prompt lyrics ───────────────────────────
def prompt_lyrics():
    print()
    print(f"  {C.BLD}embed lyrics?{C.RST}")
    print()
    print(f"    {C.YLW}1{C.RST})  yes")
    print(f"    {C.YLW}2{C.RST})  no {C.DIM}─{C.RST} default")
    print()
    try:
        choice = input("    [1/2, default 2]: ").strip()
    except EOFError:
        choice = ""

    embed = choice == "1"
    print(f"  {C.GRN}✓{C.RST} {C.BLD}{'yes' if embed else 'no'}{C.RST}")
    return embed


# ── build format-specific flags ─────────────
def build_format_flags(audio_format):
    extra_flags = []
    if audio_format == "mp3":
        # VBR q0 = best quality for mp3
        extra_flags += ["--audio-quality", "0"]
        # jpeg embeds way more reliably in ID3 tags than png
        thumb_convert = "jpg"
        thumb_codec = "mjpeg"
    else:
        thumb_convert = "png"
        thumb_codec = "png"
    return extra_flags, thumb_convert, thumb_codec


# ── count downloaded files ──────────────────
def count_files(audio_format, dir_mode):
    cwd = Path.cwd()
    ext = f".{audio_format}"

    try:
        if dir_mode == "album_folder":
            # find the most recently modified subdirectory
            subdirs = [d for d in cwd.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if subdirs:
                latest = max(subdirs, key=lambda d: d.stat().st_mtime)
                return len([f for f in latest.iterdir() if f.is_file() and f.suffix == ext])
        else:
            return len([f for f in cwd.iterdir() if f.is_file() and f.suffix == ext])
    except OSError:
        pass
    return 0


# ── format elapsed time ────────────────────
def format_time(seconds):
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}h {m}m {s}s"
    if seconds >= 60:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds}s"


# ── process lyrics ──────────────────────────
def process_lyrics(info_json_path, embed_lyrics):
    if not embed_lyrics or not info_json_path.exists():
        return None
        
    try:
        with open(info_json_path, "r", encoding="utf-8") as f:
            info = json.load(f)
            
        artist = info.get("artist") or info.get("creator") or info.get("uploader") or ""
        title = info.get("title") or info.get("fulltitle") or info.get("alt_title") or ""
        
        if not title:
            return None
            
        base_name = info_json_path.name[:-10]
        audio_file = None
        for ext in ["mp3", "opus", "m4a", "flac", "wav"]:
            candidate = info_json_path.with_name(f"{base_name}.{ext}")
            if candidate.exists():
                audio_file = candidate
                break
                
        if not audio_file:
            return None
            
        lrc_file = audio_file.with_suffix(".lrc")
        if lrc_file.exists():
            print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics: already embedded/saved by yt-dlp{C.RST}")
            return f"  {C.GRN}✓{C.RST} {title} (already handled)"
            
        query = urllib.parse.quote(f"{title} {artist}".strip())
        url = f"https://lrclib.net/api/search?q={query}"
        req = urllib.request.Request(url, headers={"User-Agent": "ytmusic-dl (https://github.com/debarkak/ytmusic-dl)"})
        
        retries = 2
        data = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt == retries - 1:
                    return f"  {C.RED}✗{C.RST} {title} (error: {e})"
                time.sleep(1)

        if data:
            lyrics = data[0].get("syncedLyrics") or data[0].get("plainLyrics")
            if lyrics:
                with open(lrc_file, "w", encoding="utf-8") as lf:
                    lf.write(lyrics)
                    
                embedded = False
                if mutagen:
                    try:
                        ext = audio_file.suffix.lower()
                        if ext == ".mp3":
                            audio = ID3(audio_file)
                            audio.delall("USLT")
                            audio.add(USLT(encoding=Encoding.UTF8, lang='eng', desc='', text=lyrics))
                            audio.save(v2_version=3)
                            embedded = True
                        elif ext == ".flac":
                            audio = FLAC(audio_file)
                            audio["LYRICS"] = lyrics
                            audio.save()
                            embedded = True
                        elif ext == ".m4a":
                            audio = MP4(audio_file)
                            audio["\xa9lyr"] = [lyrics]
                            audio.save()
                            embedded = True
                        elif ext == ".opus":
                            audio = OggOpus(audio_file)
                            audio["LYRICS"] = lyrics
                            audio.save()
                            embedded = True
                    except Exception:
                        pass
                            
                if embedded:
                    print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics embedded & saved as .lrc{C.RST}")
                    return f"  {C.GRN}✓{C.RST} {title} (embedded & saved as .lrc)"
                else:
                    print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics saved as .lrc{C.RST}")
                    return f"  {C.GRN}✓{C.RST} {title} (saved as .lrc)"
            else:
                print(f"  {C.YLW}!{C.RST} {C.DIM}No lyrics on lrclib{C.RST}")
                return f"  {C.YLW}!{C.RST} {C.DIM}{title} (no lyrics on lrclib){C.RST}"
        else:
            print(f"  {C.YLW}!{C.RST} {C.DIM}Not found on lrclib{C.RST}")
            return f"  {C.YLW}!{C.RST} {C.DIM}{title} (not found on lrclib){C.RST}"
    except Exception as e:
        return f"  {C.RED}✗{C.RST} {info_json_path.name} (error: {e})"
    finally:
        try:
            info_json_path.unlink()
        except OSError:
            pass


# ── run download ────────────────────────────
def run_download(url, audio_format, output_template, dir_mode, embed_lyrics, verbose=False):
    extra_flags, thumb_convert, thumb_codec = build_format_flags(audio_format)

    section("downloading")

    print(f"  {C.BLD}url{C.RST}        {C.CYN}{url}{C.RST}")
    print(f"  {C.BLD}format{C.RST}     {audio_format}")
    print(f"  {C.BLD}mode{C.RST}       {dir_mode}")
    print()
    print(f"  {C.DIM}┌ metadata: embedded{C.RST}")
    print(f"  {C.DIM}├ thumbnails: embedded (cropped to square){C.RST}")
    if audio_format == "mp3":
        print(f"  {C.DIM}├ mp3 quality: VBR q0 (best){C.RST}")
        print(f"  {C.DIM}├ thumbnail format: jpg (ID3 compat){C.RST}")
    print(f"  {C.DIM}├ track numbering: from playlist index{C.RST}")
    if embed_lyrics:
        print(f"  {C.DIM}├ lyrics: embedded or saved as .lrc{C.RST}")
    print(f"  {C.DIM}├ skip existing: yes{C.RST}")
    print(f"  {C.DIM}└ concurrent fragments: {FRAGMENTS}{C.RST}")
    print()

    # build the yt-dlp command
    # crop thumbnail to square using the smaller dimension
    # uses min() instead of if(gt()) to avoid single-quote quoting
    # issues on windows — yt-dlp uses shlex to parse the ppa arg, so we
    # need double backslashes here so ffmpeg gets a single escaped comma
    crop_filter = r"crop=min(iw\\,ih):min(iw\\,ih)"
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", audio_format,
        *extra_flags,
        "-o", output_template,
        "--embed-metadata",
        "--embed-thumbnail",
        "--convert-thumbnails", thumb_convert,
        "--ppa", f"ThumbnailsConvertor+ffmpeg_o:-c:v {thumb_codec} -vf {crop_filter}",
        "--parse-metadata", "playlist_index:%(track_number)s",
        "--no-overwrites",
        "--no-write-playlist-metafiles",
        "--concurrent-fragments", str(FRAGMENTS),
    ]

    if embed_lyrics:
        cmd.extend([
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", "all",
            "--embed-subs",
            "--convert-subs", "lrc",
            "--write-info-json",
        ])

    cmd.append(url)

    start_time = time.time()

    # run yt-dlp with streaming output so we can inject per-song separators
    # merges stderr into stdout since yt-dlp writes most output to stderr
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_subprocess_kwargs(),
        )
    except FileNotFoundError:
        # yt-dlp binary not found (shouldn't happen after dep check, but just in case)
        print(f"\n  {C.RED}✗{C.RST} couldn't run yt-dlp, is it in your PATH?")
        sys.exit(1)

    # patterns for parsing yt-dlp output
    item_pattern = re.compile(r"\[download\] Downloading item (\d+) of (\d+)")
    dest_pattern = re.compile(
        r"\[download\]\s+(?:Destination:\s*)?(?:.*?[\\/])?(?:\d+\s*-\s*)?(.+?)\.\w+"
    )
    progress_pattern = re.compile(r"\[download\]\s+([\d\.]+)%")
    info_json_pattern = re.compile(r"\[info\] Writing video metadata as JSON to:\s+(.+?\.info\.json)")

    current_track = 0
    total_tracks = 0
    header_printed = False
    last_was_progress = False
    saved_progress_bar = f"[{C.BLU}{'█'*30}{C.RST}] 100.0%"
    
    current_info_json = None
    lyrics_results = []

    for line in process.stdout:
        line = line.rstrip("\n")
        
        # detect new track: [download] Downloading item X of Y
        m = item_pattern.search(line)
        if m:
            if last_was_progress: print(); last_was_progress = False
            
            # process lyrics for the PREVIOUS track before starting this new one
            if header_printed and current_info_json:
                res = process_lyrics(Path(current_info_json), embed_lyrics)
                if res: lyrics_results.append(res)
                current_info_json = None
                
            # close the previous track's block
            if header_printed:
                hr(C.CYN)
                print()
            current_track = int(m.group(1))
            total_tracks = int(m.group(2))
            header_printed = False
            if verbose: print(line)
            continue
            
        # track info JSON path
        m_info = info_json_pattern.search(line)
        if m_info:
            current_info_json = m_info.group(1)

        # grab song name from destination / already-downloaded line
        if not header_printed:
            m2 = dest_pattern.search(line)
            if m2:
                if last_was_progress: print(); last_was_progress = False
                song_name = m2.group(1)
                track_info = f"  {C.YLW}[{current_track}/{total_tracks}]{C.RST}" if total_tracks > 0 else ""
                hr(C.CYN)
                print(f"  {C.MGN}{C.BLD}♫  {song_name}{C.RST}{track_info}")
                hr(C.CYN)
                header_printed = True
                if verbose: print(line)
                continue

        # grab progress
        mp = progress_pattern.search(line)
        if mp and header_printed:
            pct_str = mp.group(1)
            try:
                pct = float(pct_str)
                bar_len = 30
                filled = int(bar_len * pct / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                eta_match = re.search(r"ETA\s+([\d:]+)", line)
                eta = eta_match.group(1) if eta_match else ""
                eta_str = f" ETA {eta}" if eta else ""
                
                saved_progress_bar = f"[{C.BLU}{bar}{C.RST}] {pct:>5.1f}%{C.DIM}{eta_str}{C.RST}"
                sys.stdout.write(f"\r  {C.DIM}Downloading:{C.RST} {saved_progress_bar}\033[K")
                sys.stdout.flush()
                last_was_progress = True
            except ValueError:
                pass
            if verbose:
                print()
                print(line)
                last_was_progress = False
            continue
            
        # print errors or warnings
        if "ERROR:" in line or "WARNING:" in line:
            if last_was_progress: print(); last_was_progress = False
            print(f"  {C.YLW}{line}{C.RST}")
            continue

        # post-processing status indicators
        if not verbose and ("[ExtractAudio]" in line or "[EmbedThumbnail]" in line or "[Metadata]" in line):
            status = ""
            if "[ExtractAudio]" in line:
                status = f" {C.DIM}(Converting audio...){C.RST}"
            elif "[Metadata]" in line:
                status = f" {C.DIM}(Adding metadata...){C.RST}"
            elif "[EmbedThumbnail]" in line:
                status = f" {C.DIM}(Embedding thumbnail...){C.RST}"
            
            # Use a full 100% bar for processing if we skipped downloading because it existed
            if "Downloading" not in saved_progress_bar:
                 saved_progress_bar = f"[{C.BLU}{'█'*30}{C.RST}] 100.0%"
                 
            sys.stdout.write(f"\r  {C.DIM}Processing: {C.RST} {saved_progress_bar}{status}\033[K")
            sys.stdout.flush()
            last_was_progress = True
            continue

        # pass everything else through if verbose
        if verbose:
            if last_was_progress: print(); last_was_progress = False
            print(line)

    process.wait()
    if last_was_progress: print(); last_was_progress = False
    
    # Process the last track's lyrics (or single-video download)
    if header_printed and current_info_json:
        res = process_lyrics(Path(current_info_json), embed_lyrics)
        if res: lyrics_results.append(res)
        current_info_json = None
        
    exit_code = process.returncode

    # close the last track's block
    if header_printed:
        hr(C.CYN)

    # Print final lyrics summary if applicable
    if embed_lyrics and lyrics_results:
        print()
        section("lyrics summary")
        for res in lyrics_results:
            print(res)

    elapsed = int(time.time() - start_time)
    time_str = format_time(elapsed)

    print()

    if exit_code != 0:
        hr(C.RED)
        print(f"  {C.RED}{C.BLD}✗ yt-dlp failed{C.RST} {C.DIM}(exit code {exit_code}){C.RST}")
        print(f"  {C.DIM}check the url and try again{C.RST}")
        hr(C.RED)
        sys.exit(exit_code)

    file_count = count_files(audio_format, dir_mode)

    hr(C.GRN)
    print(f"  {C.GRN}{C.BLD}✓ done, enjoy{C.RST}")
    if file_count > 0:
        print(f"  {C.DIM}tracks:{C.RST} {C.BLD}{file_count}{C.RST}")
    print(f"  {C.DIM}time:{C.RST}   {C.BLD}{time_str}{C.RST}")
    if dir_mode in ("album_folder", "artist_folder"):
        print(f"  {C.DIM}folder:{C.RST} {C.BLD}{Path.cwd()}{C.RST}")
    else:
        print(f"  {C.DIM}files:{C.RST}  {C.BLD}{Path.cwd()}{C.RST}")
    hr(C.GRN)


# ── artist scraper ──────────────────────────
def fetch_artist_discography(url):
    print(f"\n  {C.DIM}Scraping artist page...{C.RST}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
    except Exception as e:
        print(f"  {C.RED}✗{C.RST} Failed to fetch artist page: {e}")
        return []

    options = []
    for match in re.finditer(r"initialData\.push\({path:\s*'\\/browse'.*?data:\s*'(.*?)'}\)", html):
        raw_data = match.group(1)
        try:
            decoded_data = codecs.decode(raw_data.encode('utf-8'), 'unicode_escape')
            data = json.loads(decoded_data)
        except Exception:
            continue

        def find_shelves(obj):
            if isinstance(obj, dict):
                if "musicCarouselShelfRenderer" in obj:
                    yield obj["musicCarouselShelfRenderer"]
                for v in obj.values():
                    yield from find_shelves(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from find_shelves(v)

        shelves = list(find_shelves(data))
        for shelf in shelves:
            header = shelf.get("header", {}).get("musicCarouselShelfBasicHeaderRenderer", {}).get("title", {}).get("runs", [{}])[0].get("text", "")
            if header not in ["Albums", "Singles & EPs"]:
                continue
            
            for item in shelf.get("contents", []):
                renderer = item.get("musicTwoRowItemRenderer")
                if renderer:
                    title = renderer.get("title", {}).get("runs", [{}])[0].get("text", "Unknown")
                    browse_id = renderer.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                    if browse_id:
                        if browse_id.startswith("MPREb_"):
                            url = f"https://music.youtube.com/browse/{browse_id}"
                        else:
                            url = f"https://music.youtube.com/playlist?list={browse_id}"
                        options.append((f"{title} ({header})", url))
    return options

def get_char():
    try:
        import msvcrt
        return msvcrt.getch().decode('utf-8')
    except ImportError:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch += sys.stdin.read(2)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def interactive_select(options):
    if not options:
        return []
    
    selected = [False] * len(options)
    cursor = 0
    
    # Hide cursor
    sys.stdout.write("\033[?25l")
    
    def render():
        # Move up if not first render
        if render.rendered:
            sys.stdout.write(f"\033[{len(options) + 2}A")
        
        print(f"\n  {C.BLD}Select releases to download (Space to toggle, Enter to confirm, Up/Down to navigate):{C.RST}")
        for i, (title, _) in enumerate(options):
            marker = f"{C.BLU}❯{C.RST}" if i == cursor else " "
            checkbox = f"[{C.GRN}x{C.RST}]" if selected[i] else "[ ]"
            color = C.BLD if i == cursor else C.DIM
            print(f"  {marker} {checkbox} {color}{title}{C.RST}\033[K")
        sys.stdout.flush()
        render.rendered = True

    render.rendered = False
    render()
    
    while True:
        c = get_char()
        if c == '\r' or c == '\n':
            break
        elif c == ' ':
            selected[cursor] = not selected[cursor]
        elif c == '\x1b[A': # Up
            cursor = max(0, cursor - 1)
        elif c == '\x1b[B': # Down
            cursor = min(len(options) - 1, cursor + 1)
        elif c == 'q':
            sys.stdout.write("\033[?25h\n")
            sys.exit(0)
        render()
        
    # Show cursor
    sys.stdout.write("\033[?25h\n")
    
    return [options[i][1] for i, is_sel in enumerate(selected) if is_sel]

# ── main ────────────────────────────────────
def main():
    arg_url = None
    verbose = False
    
    for arg in sys.argv[1:]:
        if arg in ("-h", "--help"):
            print(f"Usage: {sys.argv[0]} [-v] [URL]")
            sys.exit(0)
        elif arg in ("-v", "--verbose"):
            verbose = True
        else:
            if arg_url is None:
                arg_url = arg

    try:
        banner()
        check_deps()

        url = prompt_url(arg_url)
        
        is_artist_channel = "/channel/" in url or "/c/" in url or "@" in url
        urls_to_download = [url]
        
        if is_artist_channel:
            options = fetch_artist_discography(url)
            if options:
                urls_to_download = interactive_select(options)
                if not urls_to_download:
                    print(f"\n  {C.RED}✗{C.RST} No items selected. Exiting.")
                    sys.exit(0)
            else:
                print(f"  {C.YLW}!{C.RST} Could not find albums/singles natively. Falling back to regular download.")

        audio_format = prompt_format()
        output_template, dir_mode = prompt_directory()
        embed_lyrics = prompt_lyrics()

        for idx, target_url in enumerate(urls_to_download):
            if len(urls_to_download) > 1:
                print(f"\n  {C.MGN}══════════════════════════════════════════{C.RST}")
                print(f"  {C.BLD}Processing batch item {idx+1} of {len(urls_to_download)}{C.RST}")
                print(f"  {C.MGN}══════════════════════════════════════════{C.RST}")
            run_download(target_url, audio_format, output_template, dir_mode, embed_lyrics, verbose)
            
    except KeyboardInterrupt:
        sys.stdout.write("\033[?25h\n") # ensure cursor shown
        handle_interrupt(None, None)
    finally:
        reset_colors()


if __name__ == "__main__":
    main()
