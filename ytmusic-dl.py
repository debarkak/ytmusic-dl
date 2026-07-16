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
import threading
import random

LRCLIB_STRIKES = 0

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


# ── terminal styling ──────────────────────────
class C:
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
CURRENT_PROCESS = None

def handle_interrupt(sig, frame):
    global CURRENT_PROCESS
    print(f"\n{C.RST}{C.RED}{C.BLD}  ✗ interrupted{C.RST}")
    
    if CURRENT_PROCESS:
        print(f"  {C.DIM}Terminating yt-dlp...{C.RST}")
        try:
            CURRENT_PROCESS.terminate()
            CURRENT_PROCESS.wait(timeout=2)
        except Exception:
            try:
                CURRENT_PROCESS.kill()
            except Exception:
                pass
                
    sys.stdout.write("\033[?25h\n") # show cursor
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
        template = "%(folder_artist|uploader)s/%(album,playlist_title,title)s/%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "artist_folder"
    else:
        print(f"    {C.YLW}!{C.RST} {C.DIM}not valid, going with album folder{C.RST}")
        template = "%(album,playlist_title,title)s/%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        mode = "album_folder"

    print(f"  {C.GRN}✓{C.RST} {C.BLD}{mode}{C.RST}")
    return template, mode


# ── prompt lyrics ───────────────────────────
def prompt_lyrics():
    print(f"  {C.BLD}lyrics?{C.RST}\n")
    print(f"    1)  none")
    print(f"    2)  save as file")
    if mutagen is None:
        print(f"    3)  embed  {C.RED}(disabled: pip install mutagen){C.RST}")
        print(f"    4)  both   {C.RED}(disabled: pip install mutagen){C.RST}")
    else:
        print(f"    3)  embed  {C.DIM}← default{C.RST}")
        print(f"    4)  both")
    print()
    
    choice = input(f"    {C.DIM}[1-4, default 3]: {C.RST}").strip()
    
    if not choice:
        choice = "3"
        
    if mutagen is None and choice in ("3", "4"):
        print(f"  {C.YLW}!{C.RST} mutagen not installed, falling back to 'save as file'\n")
        return "file"
    
    if choice == "1":
        print(f"  {C.GRN}✓{C.RST} none\n")
        return "none"
    elif choice == "2":
        print(f"  {C.GRN}✓{C.RST} save as file\n")
        return "file"
    elif choice == "4":
        print(f"  {C.GRN}✓{C.RST} both\n")
        return "both"
    else:
        print(f"  {C.GRN}✓{C.RST} embed\n")
        return "embed"


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
def process_lyrics(info_json_path, lyrics_mode, state=None, verbose=False):
    global LRCLIB_STRIKES
    
    if not info_json_path.exists():
        return None
        
    if LRCLIB_STRIKES >= 5:
        if state and not verbose:
            state.song_pct = 95.0
            state.song_status = "Lyrics skipped (API offline)"
            render_progress(state)
        return None
        
    if state and not verbose and lyrics_mode != "none":
        state.song_pct = 95.0
        state.song_status = "Fetching lyrics..."
        render_progress(state)
        
    try:
        with open(info_json_path, "r", encoding="utf-8") as f:
            info = json.load(f)
            
        artist = info.get("artist") or info.get("creator") or info.get("uploader") or ""
        title = info.get("title") or info.get("fulltitle") or info.get("alt_title") or ""
        
        if not title:
            return None
            
        base_name = info_json_path.name[:-10]
        audio_file = None
        current_ext = None
        for ext in [".mp3", ".opus", ".m4a", ".flac", ".wav"]:
            candidate = info_json_path.with_name(f"{base_name}{ext}")
            if candidate.exists():
                audio_file = candidate
                current_ext = ext
                break
                
        if not audio_file:
            return None
            
        # --- Metadata Cleanup ---
        try:
            if current_ext == ".mp3":
                audio = ID3(audio_file)
                keys_to_del = [k for k in audio.keys() if k.startswith("COMM") or k.startswith("TXXX:purl") or k.startswith("TXXX:comment") or k.startswith("TXXX:synopsis") or k.startswith("TXXX:description")]
                for k in keys_to_del:
                    audio.pop(k, None)
                audio.save(v2_version=3)
            elif current_ext == ".m4a":
                audio = MP4(audio_file)
                if "\xa9cmt" in audio: del audio["\xa9cmt"]
                if "----:com.apple.iTunes:purl" in audio: del audio["----:com.apple.iTunes:purl"]
                if "\xa9des" in audio: del audio["\xa9des"]
                audio.save()
            elif current_ext == ".flac":
                audio = FLAC(audio_file)
                for k in ["COMMENT", "PURL", "DESCRIPTION", "SYNOPSIS"]:
                    if k in audio: del audio[k]
                audio.save()
            elif current_ext == ".opus":
                audio = OggOpus(audio_file)
                for k in ["COMMENT", "PURL", "DESCRIPTION", "SYNOPSIS"]:
                    if k in audio: del audio[k]
                audio.save()
        except Exception:
            pass
            
        if lyrics_mode == "none":
            return None
            
        lrc_file = audio_file.with_suffix(".lrc")
        if lrc_file.exists():
            print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics: already embedded/saved by yt-dlp{C.RST}")
            return f"  {C.GRN}✓{C.RST} {title} (already handled)"
            
        query = urllib.parse.quote(f"{title} {artist}".strip())
        url = f"https://lrclib.net/api/search?q={query}"
        req = urllib.request.Request(url, headers={"User-Agent": "ytmusic-dl (https://github.com/debarkak/ytmusic-dl)"})
        
        retries = 25
        data = None
        for attempt in range(retries):
            if state and not verbose and lyrics_mode != "none":
                state.song_pct = 90.0 + (attempt * 0.8)
                if attempt == 0:
                    state.song_status = "Fetching lyrics..."
                else:
                    state.song_status = f"Fetching lyrics (retry {attempt}/{retries})..."
                render_progress(state)
                
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                    
                if state and not verbose and lyrics_mode != "none":
                    state.song_pct = 99.0
                    state.song_status = "Embedding lyrics..."
                    render_progress(state)
                break
            except Exception as e:
                if attempt == retries - 1:
                    LRCLIB_STRIKES += 1
                    return f"  {C.RED}✗{C.RST} {title} (error: {e})"
                time.sleep(random.randint(3, 16))

        if data:
            LRCLIB_STRIKES = 0
            lyrics = data[0].get("syncedLyrics") or data[0].get("plainLyrics")
            if lyrics:
                lrc_path = info_json_path.with_suffix("").with_suffix(".lrc")
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(lyrics)
                    
                embedded = False
                if lyrics_mode in ["embed", "both"]:
                    try:
                        # use the current_ext we found earlier!
                        if current_ext == ".mp3":
                            audio = ID3(audio_file)
                            audio.delall("USLT")
                            audio.add(USLT(encoding=Encoding.UTF8, lang='eng', desc='', text=lyrics))
                            audio.save(v2_version=3)
                            embedded = True
                        elif current_ext == ".m4a":
                            audio = MP4(audio_file)
                            audio["\xa9lyr"] = [lyrics]
                            audio.save()
                            embedded = True
                        elif current_ext == ".flac":
                            audio = FLAC(audio_file)
                            audio["LYRICS"] = lyrics
                            audio.save()
                            embedded = True
                        elif current_ext == ".opus":
                            audio = OggOpus(audio_file)
                            audio["LYRICS"] = lyrics
                            audio.save()
                            embedded = True
                    except Exception:
                        pass
                        
                if lyrics_mode == "embed" and embedded:
                    try:
                        lrc_path.unlink()
                    except OSError:
                        pass
                            
                if lyrics_mode == "embed":
                    if embedded:
                        if verbose: print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics embedded{C.RST}")
                        res = f"  {C.GRN}✓{C.RST} {title} (embedded)"
                    else:
                        if verbose: print(f"  {C.RED}✗{C.RST} {C.DIM}Lyrics embed failed{C.RST}")
                        res = f"  {C.RED}✗{C.RST} {title} (embed failed)"
                elif lyrics_mode == "both":
                    if embedded:
                        if verbose: print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics embedded & saved as .lrc{C.RST}")
                        res = f"  {C.GRN}✓{C.RST} {title} (embedded & saved as .lrc)"
                    else:
                        if verbose: print(f"  {C.RED}✗{C.RST} {C.DIM}Lyrics saved, but embed failed{C.RST}")
                        res = f"  {C.RED}✗{C.RST} {title} (saved, embed failed)"
                else:
                    if verbose: print(f"  {C.GRN}✓{C.RST} {C.DIM}Lyrics saved as .lrc{C.RST}")
                    res = f"  {C.GRN}✓{C.RST} {title} (saved as .lrc)"
            else:
                if verbose: print(f"  {C.YLW}!{C.RST} {C.DIM}No lyrics on lrclib{C.RST}")
                res = f"  {C.YLW}!{C.RST} {C.DIM}{title} (no lyrics on lrclib){C.RST}"
        else:
            if verbose: print(f"  {C.YLW}!{C.RST} {C.DIM}Not found on lrclib{C.RST}")
            res = f"  {C.YLW}!{C.RST} {C.DIM}{title} (not found on lrclib){C.RST}"
    except Exception as e:
        res = f"  {C.RED}✗{C.RST} {info_json_path.name} (error: {e})"
    finally:
        try:
            info_json_path.unlink()
        except OSError:
            pass

    if state and not verbose:
        state.song_pct = 100.0
        state.song_status = "Done"
        render_progress(state)
    return res

class UIState:
    def __init__(self):
        self.batch_idx = 0
        self.batch_total = 0
        self.album_track = 0
        self.album_total = 0
        self.song_name = "..."
        self.song_pct = 0.0
        self.song_status = "Waiting"
        self.song_eta = ""
        self.rendered_lines = 0
        self.album_start_time = 0.0
        self.album_eta_seconds = None
        self.lock = threading.Lock()
        self.is_active = True

def animate_progress(state):
    while state.is_active:
        if state.song_status not in ["Downloading", "Done", "Converting audio", "Adding metadata", "Embedding thumbnail"]:
            render_progress(state)
        time.sleep(0.05)

def render_progress(state):
    with state.lock:
        # Hide cursor
        sys.stdout.write("\033[?25l")
        
        if state.rendered_lines > 0:
            sys.stdout.write(f"\033[{state.rendered_lines}A")
            
        lines = []
        
        # Calculate dynamic fractions
        completed_tracks = max(0, state.album_track - 1)
        song_fraction = state.song_pct / 100.0
        album_fraction = (completed_tracks + song_fraction) / state.album_total if state.album_total > 0 else 0.0
        
        completed_batches = max(0, state.batch_idx - 1)
        overall_fraction = (completed_batches + album_fraction) / state.batch_total if state.batch_total > 0 else 0.0
        
        # Overall
        overall_pct = overall_fraction * 100
        bb = int(30 * overall_fraction)
        batch_bar = "█" * bb + "░" * (30 - bb)
        lines.append(f"  {C.DIM}Overall:{C.RST} [{C.BLU}{batch_bar}{C.RST}] {overall_pct:>5.1f}% ─ {state.batch_idx}/{state.batch_total} batches")
        
        # Album
        album_pct = album_fraction * 100
        ab = int(30 * album_fraction)
        album_bar = "█" * ab + "░" * (30 - ab)
        
        is_indeterminate = state.song_status not in ["Downloading", "Done", "Converting audio", "Adding metadata", "Embedding thumbnail"]
        
        album_eta_str = ""
        if state.album_total > 0 and getattr(state, "album_start_time", 0.0) > 0 and 0 < album_fraction < 1.0:
            if not is_indeterminate:
                elapsed = time.time() - state.album_start_time
                raw_remaining = (elapsed / album_fraction) - elapsed
                if raw_remaining > 0:
                    if state.album_eta_seconds is None:
                        state.album_eta_seconds = raw_remaining
                    else:
                        state.album_eta_seconds = 0.95 * state.album_eta_seconds + 0.05 * raw_remaining
            
            if getattr(state, "album_eta_seconds", None) is not None:
                mins, secs = divmod(int(state.album_eta_seconds), 60)
                hrs, mins = divmod(mins, 60)
                if hrs > 0:
                    album_eta_str = f" ETA {hrs:02d}:{mins:02d}:{secs:02d}"
                else:
                    album_eta_str = f" ETA {mins:02d}:{secs:02d}"
                        
        lines.append(f"  {C.DIM}Album:  {C.RST} [{C.CYN}{album_bar}{C.RST}] {album_pct:>5.1f}% ─ {state.album_track}/{state.album_total} tracks{C.DIM}{album_eta_str}{C.RST}")
        
        # Song
        if is_indeterminate:
            # Bouncing animation (30 chars wide, 3 char block)
            pos = int(time.time() * 20) % 54
            if pos >= 27:
                pos = 54 - pos
            song_bar = " " * pos + "███" + " " * (27 - pos)
            song_bar_display = f"[{C.MGN}{song_bar}{C.RST}]"
        else:
            sb = int(30 * (state.song_pct / 100))
            song_bar = "█" * sb + "░" * (30 - sb)
            status_color = C.DIM if state.song_status == "Done" else C.MGN
            song_bar_display = f"[{status_color}{song_bar}{C.RST}]"
            
        eta_str = f" ETA {state.song_eta}" if state.song_eta and state.song_status == "Downloading" else ""
        lines.append(f"  {C.DIM}Song:   {C.RST} {song_bar_display} {state.song_pct:>5.1f}% ({state.song_status}){C.DIM}{eta_str} ─ {state.song_name}{C.RST}")
        
        for line in lines:
            sys.stdout.write(f"\r{line}\033[K\n")
        sys.stdout.flush()
        state.rendered_lines = len(lines)

# ── run download ────────────────────────────
def run_download(url, audio_format, output_template, dir_mode, lyrics_mode, state=None, verbose=False, sync_dir=None):
    if sync_dir:
        output_template = r"%(track_number,playlist_index,autonumber)02d - %(title)s.%(ext)s"
        
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
    if lyrics_mode != "none":
        print(f"  {C.DIM}├ lyrics: {lyrics_mode}{C.RST}")
    print(f"  {C.DIM}├ metadata tags: cleaned{C.RST}")
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
        "--ignore-errors",
        "--extractor-args", "youtube:player_client=android_vr,web",
        "--parse-metadata", "%(playlist_channel|playlist_uploader|channel|uploader|artist)s:(?P<folder_artist>[^,&，]+)",
        "--replace-in-metadata", "folder_artist", r"[\uac00-\ud7a3]+\s*\((.+?)\)", r"\1",
        "--replace-in-metadata", "folder_artist", r"\s*-\s*Topic\s*", "",
        "--replace-in-metadata", "folder_artist", r"^\s+|\s+$", "",
        "--retries", "25",
        "--fragment-retries", "25",
        "--retry-sleep", "linear=3::16",
        "--retry-sleep", "fragment:linear=3::16",
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", audio_format,
        *extra_flags,
        "-o", output_template,
        "--embed-metadata",
        "--parse-metadata", "playlist_index:%(track_number)s",
        "--parse-metadata", "%(artist)s:%(album_artist)s",
        "--parse-metadata", "%(track,title)s:%(title)s",
        "--parse-metadata", "%(release_year,upload_date)s:%(date)s",
        "--parse-metadata", r"artist:(?P<meta_primary_artist>.+?)(?:\s*[,&]|feat|ft|$)",
        "--replace-in-metadata", "artist,album_artist,meta_primary_artist", r"\s*\([^)]*[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff][^)]*\)", "",
        "--parse-metadata", "NA:%(comment)s",
        "--parse-metadata", "NA:%(synopsis)s",
        "--parse-metadata", "NA:%(description)s",
        "--embed-thumbnail",
        "--convert-thumbnails", thumb_convert,
        "--ppa", f"ThumbnailsConvertor+ffmpeg_o:-c:v {thumb_codec} -vf {crop_filter}",
        "--no-overwrites",
        "--no-write-playlist-metafiles",
        "--concurrent-fragments", str(FRAGMENTS),
    ]

    if lyrics_mode != "none":
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
    global CURRENT_PROCESS

    # run yt-dlp with streaming output so we can inject per-song separators
    # merges stderr into stdout since yt-dlp writes most output to stderr
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(sync_dir) if sync_dir else None,
            **_subprocess_kwargs(),
        )
        CURRENT_PROCESS = process
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
    retry_pattern = re.compile(r"Retrying\s+\((\d+)/(\d+)\)")

    header_printed = False
    last_was_progress = False
    
    current_info_json = None
    lyrics_results = []
    
    if state and not verbose:
        state.song_pct = 0.0
        state.song_status = "Waiting"
        state.album_track = 0
        state.album_total = 1 # default
        render_progress(state)

    try:
        for line in process.stdout:
            line = line.rstrip("\n")
            
            # detect new track: [download] Downloading item X of Y
            m = item_pattern.search(line)
            if m:
                if last_was_progress: 
                    if verbose: print()
                    last_was_progress = False
                
                # process lyrics for the PREVIOUS track before starting this new one
                if current_info_json:
                    res = process_lyrics(Path(current_info_json), lyrics_mode, state, verbose)
                    if res: lyrics_results.append(res)
                    current_info_json = None
                    
                # close the previous track's block
                if header_printed and verbose:
                    hr(C.CYN)
                    print()
                    
                if state:
                    state.album_track = int(m.group(1))
                    state.album_total = int(m.group(2))
                    state.song_pct = 0.0
                    state.song_status = "Waiting"
                    if not verbose: render_progress(state)
                
                header_printed = False
                if verbose: print(line)
                continue
                
            # track info JSON path
            m_info = info_json_pattern.search(line)
            if m_info:
                current_info_json = m_info.group(1)
                if dir_mode in ["album_folder", "artist_folder"]:
                    album_dir = Path(current_info_json).parent
                    sync_file = album_dir / ".ytmusic-dl.json"
                    if not sync_file.exists():
                        try:
                            sync_data = {
                                "url": url,
                                "audio_format": audio_format,
                                "dir_mode": dir_mode,
                                "lyrics_mode": lyrics_mode
                            }
                            with open(sync_file, "w", encoding="utf-8") as f:
                                json.dump(sync_data, f, indent=2)
                            if IS_WINDOWS:
                                import ctypes
                                FILE_ATTRIBUTE_HIDDEN = 0x02
                                ctypes.windll.kernel32.SetFileAttributesW(str(sync_file), FILE_ATTRIBUTE_HIDDEN)
                        except Exception:
                            pass

            # detect retry
            m_retry = retry_pattern.search(line)
            if m_retry:
                if state and not verbose:
                    current, total = m_retry.group(1), m_retry.group(2)
                    state.song_status = f"Retrying ({current}/{total})..."
                    render_progress(state)
                if verbose: print(line)
                continue

            # grab song name from destination / already-downloaded line
            if not header_printed:
                m2 = dest_pattern.search(line)
                if m2:
                    if last_was_progress: 
                        if verbose: print()
                        last_was_progress = False
                    song_name = m2.group(1)
                    
                    if state:
                        state.song_name = song_name
                        state.song_pct = 0.0
                        state.song_status = "Downloading"
                        if state.album_track == 0: # If item_pattern was never hit
                            state.album_track = 1
                        if not verbose: render_progress(state)
                    
                    if verbose:
                        track_info = f"  {C.YLW}[{state.album_track if state else 1}/{state.album_total if state else 1}]{C.RST}"
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
                eta_match = re.search(r"ETA\s+([\d:]+)", line)
                eta = eta_match.group(1) if eta_match else ""
                
                try:
                    pct = float(pct_str)
                    if state and not verbose:
                        state.song_pct = pct * 0.75 # 0-75%
                        state.song_status = "Downloading"
                        if eta: state.song_eta = eta
                        render_progress(state)
                    elif verbose:
                        bar_len = 30
                        filled = int(bar_len * pct / 100)
                        bar = "█" * filled + "░" * (bar_len - filled)
                        eta_str = f" ETA {eta}" if eta else ""
                        sys.stdout.write(f"\r  {C.DIM}Downloading:{C.RST} [{C.BLU}{bar}{C.RST}] {pct:>5.1f}%{C.DIM}{eta_str}{C.RST}\033[K")
                        sys.stdout.flush()
                    last_was_progress = True
                except ValueError:
                    pass
                if verbose:
                    # Need newline for next line if verbose but not logging progress
                    pass
                continue
                
            # print errors or warnings
            if "ERROR:" in line or "WARNING:" in line:
                if last_was_progress: 
                    if verbose: print()
                    last_was_progress = False
                
                # Since errors break our nice fixed block, we need to temporarily clear the block, 
                # print the error, and redraw it.
                if state and not verbose:
                    sys.stdout.write(f"\033[{state.rendered_lines}A")
                    sys.stdout.write("\033[J") # clear below
                    state.rendered_lines = 0
                    
                print(f"  {C.YLW}{line}{C.RST}")
                
                if state and not verbose:
                    render_progress(state)
                continue

            # post-processing status indicators
            if "[ExtractAudio]" in line or "[EmbedThumbnail]" in line or "[Metadata]" in line:
                if state and not verbose:
                    if "[ExtractAudio]" in line:
                        state.song_pct = 75.0
                        state.song_status = "Converting audio"
                    elif "[Metadata]" in line:
                        state.song_pct = 85.0
                        state.song_status = "Adding metadata"
                    elif "[EmbedThumbnail]" in line:
                        state.song_pct = 95.0
                        state.song_status = "Embedding thumbnail"
                    render_progress(state)
                elif verbose:
                    if last_was_progress: print()
                    print(line)
                last_was_progress = False
                continue

            # pass everything else through if verbose
            if verbose:
                if last_was_progress: print(); last_was_progress = False
                print(line)

    finally:
        process.stdout.close()
        process.wait()
        CURRENT_PROCESS = None
        
    if last_was_progress and verbose: print()
    last_was_progress = False
    
    # Process the last track's lyrics (or single-video download)
    if current_info_json:
        res = process_lyrics(Path(current_info_json), lyrics_mode, state, verbose)
        if res: lyrics_results.append(res)
        current_info_json = None
        
    exit_code = process.returncode

    # close the last track's block
    if header_printed and verbose:
        hr(C.CYN)

    # Print final lyrics summary if applicable
    if lyrics_mode != "none" and lyrics_results:
        # Move past the fixed block
        if state and not verbose:
            sys.stdout.write(f"\033[{state.rendered_lines}B\n")
            state.rendered_lines = 0
            
        print()
        section("lyrics summary")
        for res in lyrics_results:
            print(res)

    elapsed = int(time.time() - start_time)
    time_str = format_time(elapsed)

    print()

    if exit_code != 0:
        hr(C.RED)
        print(f"  {C.RED}{C.BLD}! yt-dlp encountered errors{C.RST} {C.DIM}(exit code {exit_code}){C.RST}")
        print(f"  {C.DIM}some tracks may have failed (e.g., 403 Forbidden). Continuing to next batch...{C.RST}")
        hr(C.RED)

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
    
    return exit_code


# ── artist scraper ──────────────────────────
def fetch_artist_discography(url):
    print(f"\n  {C.DIM}Scraping artist page...{C.RST}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
    except Exception as e:
        print(f"  {C.RED}✗{C.RST} Failed to fetch artist page: {e}")
        return None, []

    # extract artist name from title
    artist_name_match = re.search(r'<title>(.*?)</title>', html)
    artist_name = artist_name_match.group(1) if artist_name_match else None
    if artist_name and artist_name.endswith(" - YouTube Music"):
        artist_name = artist_name[:-16]
    
    # validate: if the title is garbage (e.g. "undefined", "Your browser is deprecated"),
    # fall back to yt-dlp's own uploader extraction
    bad_titles = {"undefined", "your browser is deprecated", "youtube music", ""}
    if not artist_name or artist_name.strip().lower().rstrip(".") in bad_titles:
        try:
            fallback = subprocess.run(
                ["yt-dlp", "--print", "uploader", "--playlist-items", "1", url],
                capture_output=True, text=True, timeout=30
            )
            fb_name = fallback.stdout.strip().split("\n")[0] if fallback.stdout.strip() else None
            if fb_name:
                artist_name = fb_name
                print(f"  {C.DIM}(artist name from yt-dlp: {artist_name}){C.RST}")
        except Exception:
            pass


    # extract api credentials for "See All" fetching
    api_key_match = re.search(r'"INNERTUBE_API_KEY":"(.*?)"', html)
    client_version_match = re.search(r'"clientVersion":"(.*?)"', html)
    
    api_key = api_key_match.group(1) if api_key_match else ""
    client_version = client_version_match.group(1) if client_version_match else "1.20260712.05.00"

    options = []
    seen_urls = set()
    
    def fetch_api(browse_id, params):
        if not api_key: return None
        api_url = f"https://music.youtube.com/youtubei/v1/browse?key={api_key}"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB_REMIX",
                    "clientVersion": client_version
                }
            },
            "browseId": browse_id,
            "params": params
        }
        api_req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/json"
        })
        try:
            return json.loads(urllib.request.urlopen(api_req).read().decode('utf-8'))
        except Exception:
            return None

    for match in re.finditer(r"initialData\.push\({path:\s*'\\/browse'.*?data:\s*'(.*?)'}\)", html):
        raw_data = match.group(1).replace(r"\/", "/")
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

        def extract_items(items_data, header):
            def find_items(obj):
                if isinstance(obj, dict):
                    if "musicTwoRowItemRenderer" in obj:
                        yield obj["musicTwoRowItemRenderer"]
                    for v in obj.values():
                        yield from find_items(v)
                elif isinstance(obj, list):
                    for v in obj:
                        yield from find_items(v)
                        
            for renderer in find_items(items_data):
                title = renderer.get("title", {}).get("runs", [{}])[0].get("text", "Unknown")
                b_id = renderer.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                if b_id:
                    if b_id.startswith("MPREb_"):
                        item_url = f"https://music.youtube.com/browse/{b_id}"
                    else:
                        item_url = f"https://music.youtube.com/playlist?list={b_id}"
                    if item_url not in seen_urls:
                        options.append((f"{title} ({header})", item_url))
                        seen_urls.add(item_url)

        shelves = list(find_shelves(data))
        for shelf in shelves:
            header_runs = shelf.get("header", {}).get("musicCarouselShelfBasicHeaderRenderer", {}).get("title", {}).get("runs", [{}])
            if not header_runs: continue
            header = header_runs[0].get("text", "")
            if header not in ["Albums", "Singles & EPs", "Singles", "EPs"]:
                continue
            
            nav_endpoint = header_runs[0].get("navigationEndpoint", {})
            browse_endpoint = nav_endpoint.get("browseEndpoint", {})
            see_all_id = browse_endpoint.get("browseId")
            params = browse_endpoint.get("params")
            
            if see_all_id and params:
                see_all_data = fetch_api(see_all_id, params)
                if see_all_data:
                    extract_items(see_all_data, header)
                else:
                    extract_items(shelf.get("contents", []), header)
            else:
                extract_items(shelf.get("contents", []), header)
                
    return artist_name, options

def get_char():
    try:
        import msvcrt
        return msvcrt.getch().decode('utf-8')
    except ImportError:
        import tty, termios, select, os
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            # Use os.read to bypass Python's internal sys.stdin buffer
            b = os.read(fd, 1)
            ch = b.decode('utf-8', errors='ignore')
            if ch == '\x1b':
                dr, _, _ = select.select([fd], [], [], 0.1)
                if dr:
                    b += os.read(fd, 2)
                    ch = b.decode('utf-8', errors='ignore')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def interactive_select(options):
    if not options:
        return []
    
    selected = [False] * len(options)
    cursor = 0
    window_start = 0
    max_display = 15
    search_mode = False
    search_query = ""
    
    # Hide cursor
    sys.stdout.write("\033[?25l")
    
    def render():
        nonlocal window_start, cursor
        
        filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
        if cursor >= len(filtered_indices) and filtered_indices:
            cursor = len(filtered_indices) - 1
        elif not filtered_indices:
            cursor = 0
            
        # Adjust window
        if cursor < window_start:
            window_start = cursor
        elif cursor >= window_start + max_display:
            window_start = cursor - max_display + 1
            
        display_indices = filtered_indices[window_start:window_start + max_display]
        
        # Move up if not first render
        if getattr(render, "rendered", False):
            sys.stdout.write(f"\033[{max_display + 3}A")
        
        print(f"\n  {C.BLD}Select releases to download (Space to toggle, 'a' to select all, Enter to confirm, / to search, Up/Down to navigate):{C.RST}\033[K")
        if search_mode or search_query:
            cursor_char = "█" if search_mode else ""
            print(f"  {C.CYN}Search:{C.RST} {search_query}{cursor_char}\033[K")
        else:
            print(f"  {C.DIM}(Press / to search){C.RST}\033[K")
            
        for i in range(max_display):
            if i < len(display_indices):
                actual_idx = display_indices[i]
                title = options[actual_idx][0]
                marker = f"{C.BLU}❯{C.RST}" if i + window_start == cursor else " "
                checkbox = f"[{C.GRN}x{C.RST}]" if selected[actual_idx] else "[ ]"
                color = C.BLD if i + window_start == cursor else C.DIM
                
                # Show scrolling indicators
                if i == 0 and window_start > 0:
                    prefix = f"{C.YLW}↑{C.RST} "
                elif i == len(display_indices) - 1 and window_start + len(display_indices) < len(filtered_indices):
                    prefix = f"{C.YLW}↓{C.RST} "
                else:
                    prefix = "  "
                    
                print(f"  {marker} {checkbox} {prefix}{color}{title}{C.RST}\033[K")
            else:
                print("\033[K")
                
        sys.stdout.flush()
        render.rendered = True

    render()
    
    while True:
        c = get_char()
        if search_mode:
            if c == '\r' or c == '\n' or c == '\x1b':
                search_mode = False
            elif c == '\x1b[A': # Up
                cursor = max(0, cursor - 1)
            elif c == '\x1b[B': # Down
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                if filtered_indices:
                    cursor = min(len(filtered_indices) - 1, cursor + 1)
            elif c in ('\x7f', '\x08'):
                search_query = search_query[:-1]
                window_start = 0
            elif len(c) == 1 and c.isprintable():
                search_query += c
                cursor = 0
                window_start = 0
        else:
            if c == '\r' or c == '\n':
                break
            elif c == '/':
                search_mode = True
            elif c == ' ':
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                if filtered_indices:
                    actual_idx = filtered_indices[cursor]
                    selected[actual_idx] = not selected[actual_idx]
            elif c == '\x1b[A': # Up
                cursor = max(0, cursor - 1)
            elif c == '\x1b[B': # Down
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                if filtered_indices:
                    cursor = min(len(filtered_indices) - 1, cursor + 1)
            elif c.lower() == 'a':
                filtered_indices = [i for i, (title, _) in enumerate(options) if search_query.lower() in title.lower()]
                if filtered_indices:
                    all_selected = all(selected[i] for i in filtered_indices)
                    for i in filtered_indices:
                        selected[i] = not all_selected
            elif c == 'q':
                sys.stdout.write("\033[?25h\n")
                sys.exit(0)
        render()
        
    # Show cursor
    sys.stdout.write("\033[?25h\n")
    
    return [options[i][1] for i, is_sel in enumerate(selected) if is_sel]

# ── sync mode ───────────────────────────────
def run_sync_mode(verbose=False):
    section("sync library")
    print(f"  {C.DIM}Scanning for .ytmusic-dl.json files...{C.RST}")
    
    sync_files = list(Path.cwd().rglob(".ytmusic-dl.json"))
    if not sync_files:
        print(f"\n  {C.YLW}!{C.RST} No sync files found in the current directory tree.")
        return
        
    print(f"  {C.GRN}✓{C.RST} Found {len(sync_files)} albums/directories to sync\n")
    
    ui_state = UIState()
    ui_state.batch_total = len(sync_files)
    ui_state.anim_thread = threading.Thread(target=animate_progress, args=(ui_state,), daemon=True)
    ui_state.anim_thread.start()

    failed_downloads = []
    consecutive_album_fails = 0
    
    try:
        for idx, sf in enumerate(sync_files):
            free_space = shutil.disk_usage(Path.cwd()).free
            if free_space < 500 * 1024 * 1024:
                ui_state.is_active = False
                hr(C.RED)
                print(f"  {C.RED}{C.BLD}🛑 EMERGENCY STOP: Disk Almost Full{C.RST}")
                print(f"  {C.DIM}Less than 500MB remaining. Aborting session.{C.RST}")
                hr(C.RED)
                break
                
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                if verbose: print(f"  {C.RED}✗{C.RST} Failed to read {sf}: {e}")
                continue
                
            url = data.get("url")
            audio_format = data.get("audio_format")
            dir_mode = data.get("dir_mode")
            lyrics_mode = data.get("lyrics_mode")
            
            if not all([url, audio_format, dir_mode, lyrics_mode]):
                if verbose: print(f"  {C.RED}✗{C.RST} Invalid sync file: {sf}")
                continue
                
            ui_state.batch_idx = idx + 1
            ui_state.album_start_time = time.time()
            
            if verbose or len(sync_files) > 1:
                print(f"\n  {C.MGN}══════════════════════════════════════════{C.RST}")
                print(f"  {C.BLD}Syncing batch item {idx+1} of {len(sync_files)}{C.RST}")
                print(f"  {C.DIM}Target: {sf.parent}{C.RST}")
                print(f"  {C.MGN}══════════════════════════════════════════{C.RST}")
                
            code = run_download(url, audio_format, "", dir_mode, lyrics_mode, ui_state, verbose, sync_dir=sf.parent)
            if code != 0:
                failed_downloads.append(url)
                consecutive_album_fails += 1
                if consecutive_album_fails >= 3:
                    if ui_state.rendered_lines > 0:
                        sys.stdout.write(f"\033[{ui_state.rendered_lines}B\n")
                        ui_state.rendered_lines = 0
                    print(f"\n  {C.YLW}{C.BLD}⚠️  Global Rate-Limit Tripwire Triggered!{C.RST}")
                    print(f"  {C.DIM}3 consecutive albums failed. Sleeping for 5 minutes to evade IP ban...{C.RST}")
                    ui_state.song_status = "Cooling down (5m pause)..."
                    time.sleep(300)
                    consecutive_album_fails = 0
            else:
                consecutive_album_fails = 0
                
    finally:
        ui_state.is_active = False
        
        if ui_state.rendered_lines > 0:
            sys.stdout.write(f"\033[{ui_state.rendered_lines}B\n")
            sys.stdout.write("\033[?25h") # show cursor
            ui_state.rendered_lines = 0
            
        if failed_downloads:
            hr(C.RED)
            print(f"  {C.RED}{C.BLD}⚠️  Failed Downloads Summary{C.RST}")
            print(f"  {C.DIM}The following {len(failed_downloads)} URLs encountered terminal errors during processing:{C.RST}")
            for u in failed_downloads:
                print(f"  {C.DIM}- {u}{C.RST}")
            hr(C.RED)


# ── organize mode ───────────────────────────
def run_organize_mode(verbose=False):
    section("organize library")
    print(f"  {C.DIM}Scanning current directory for messy collab folders...{C.RST}")
    
    import shutil
    
    cwd = Path.cwd()
    moved_count = 0
    removed_count = 0
    
    for folder in cwd.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue
            
        original_name = folder.name
        
        # 1. Parse primary artist (everything before , & ，)
        match = re.search(r'^([^,&，]+)', original_name)
        clean_name = match.group(1) if match else original_name
            
        # 2. Strip Korean text
        clean_name = re.sub(r'[\uac00-\ud7a3]+\s*\((.+?)\)', r'\1', clean_name)
        
        # 3. Strip " - Topic"
        clean_name = re.sub(r'\s*-\s*Topic\s*', '', clean_name)
        
        # 4. Trim whitespace
        clean_name = clean_name.strip()
        
        if not clean_name or clean_name == original_name:
            continue
            
        target_dir = cwd / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
            
        # Move all albums inside the messy folder to the clean folder
        albums_moved = 0
        for item in folder.iterdir():
            if item.name.startswith("."):
                continue
            
            dest_item = target_dir / item.name
            
            if dest_item.exists() and dest_item.is_dir() and item.is_dir():
                for sub_item in item.iterdir():
                    # We want to move everything, including hidden .ytmusic-dl.json files and .part files!
                    if not (dest_item / sub_item.name).exists():
                        shutil.move(str(sub_item), str(dest_item))
                    elif sub_item.name == ".ytmusic-dl.json":
                        # If both folders have the sync file, the one in dest is enough. Delete the redundant one.
                        sub_item.unlink()
                        
                # After moving all contents, remove the now-empty album folder
                try:
                    item.rmdir()
                except OSError:
                    pass
                albums_moved += 1
            elif not dest_item.exists():
                shutil.move(str(item), str(target_dir))
                albums_moved += 1
                
        if albums_moved > 0:
            print(f"  {C.GRN}✓{C.RST} Merged {C.YLW}'{original_name}'{C.RST} -> {C.CYN}'{clean_name}'{C.RST} ({albums_moved} items)")
            moved_count += 1
            
        try:
            folder.rmdir()
            removed_count += 1
        except OSError:
            pass
    if moved_count > 0:
        hr(C.GRN)
        print(f"  {C.GRN}{C.BLD}✓ Library organized successfully{C.RST}")
        print(f"  {C.DIM}Merged {moved_count} messy folders and removed {removed_count} empty directories.{C.RST}")
        hr(C.GRN)
    else:
        print(f"  {C.GRN}✓{C.RST} Library is already perfectly clean!\n")

# ── main ────────────────────────────────────
def main():
    arg_url = None
    verbose = False
    
    if "--sync" in sys.argv:
        verbose = "-v" in sys.argv or "--verbose" in sys.argv
        banner()
        try:
            run_sync_mode(verbose)
        except KeyboardInterrupt:
            handle_interrupt(None, None)
        finally:
            sys.stdout.write("\033[?25h\n") # ensure cursor shown
            reset_colors()
        return

    if "--organize" in sys.argv:
        verbose = "-v" in sys.argv or "--verbose" in sys.argv
        banner()
        try:
            run_organize_mode(verbose)
        except KeyboardInterrupt:
            handle_interrupt(None, None)
        finally:
            sys.stdout.write("\033[?25h\n")
            reset_colors()
        return

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
        
        artist_name = None
        if is_artist_channel:
            artist_name, options = fetch_artist_discography(url)
            if options:
                urls_to_download = interactive_select(options)
                if not urls_to_download:
                    print(f"\n  {C.RED}✗{C.RST} No items selected. Exiting.")
                    sys.exit(0)
            else:
                print(f"  {C.YLW}!{C.RST} Could not find albums/singles natively. Falling back to regular download.")

        audio_format = prompt_format()
        output_template, dir_mode = prompt_directory()
        lyrics_mode = prompt_lyrics()
        
        # Override output_template with explicit artist name if downloading from their channel
        if is_artist_channel and dir_mode == "artist_folder" and artist_name:
            clean_artist_name = re.sub(r'[\uac00-\ud7a3]+\s*\((.+?)\)', r'\1', artist_name)
            clean_artist_name = re.sub(r'\s*-\s*Topic\s*', '', clean_artist_name).strip()
            # replace the internal yt-dlp metadata placeholder with the hardcoded artist name
            output_template = output_template.replace("%(folder_artist|uploader)s", clean_artist_name, 1)
        
        ui_state = UIState()
        ui_state.batch_total = len(urls_to_download)
        ui_state.anim_thread = threading.Thread(target=animate_progress, args=(ui_state,), daemon=True)
        ui_state.anim_thread.start()

        failed_downloads = []
        consecutive_album_fails = 0

        for idx, target_url in enumerate(urls_to_download):
            free_space = shutil.disk_usage(Path.cwd()).free
            if free_space < 500 * 1024 * 1024:
                ui_state.is_active = False
                hr(C.RED)
                print(f"  {C.RED}{C.BLD}🛑 EMERGENCY STOP: Disk Almost Full{C.RST}")
                print(f"  {C.DIM}Less than 500MB remaining. Aborting session.{C.RST}")
                hr(C.RED)
                break
                
            ui_state.batch_idx = idx + 1
            ui_state.album_start_time = time.time()
            if len(urls_to_download) > 1 and verbose:
                print(f"\n  {C.MGN}══════════════════════════════════════════{C.RST}")
                print(f"  {C.BLD}Processing batch item {idx+1} of {len(urls_to_download)}{C.RST}")
                print(f"  {C.MGN}══════════════════════════════════════════{C.RST}")
                
            code = run_download(target_url, audio_format, output_template, dir_mode, lyrics_mode, ui_state, verbose)
            if code != 0:
                failed_downloads.append(target_url)
                consecutive_album_fails += 1
                if consecutive_album_fails >= 3:
                    if ui_state.rendered_lines > 0:
                        sys.stdout.write(f"\033[{ui_state.rendered_lines}B\n")
                        ui_state.rendered_lines = 0
                    print(f"\n  {C.YLW}{C.BLD}⚠️  Global Rate-Limit Tripwire Triggered!{C.RST}")
                    print(f"  {C.DIM}3 consecutive albums failed. Sleeping for 5 minutes to evade IP ban...{C.RST}")
                    ui_state.song_status = "Cooling down (5m pause)..."
                    time.sleep(300)
                    consecutive_album_fails = 0
            else:
                consecutive_album_fails = 0
            
        ui_state.is_active = False
        
        if ui_state.rendered_lines > 0:
            sys.stdout.write(f"\033[{ui_state.rendered_lines}B\n")
            sys.stdout.write("\033[?25h") # show cursor
            ui_state.rendered_lines = 0
            
        if failed_downloads:
            hr(C.RED)
            print(f"  {C.RED}{C.BLD}⚠️  Failed Downloads Summary{C.RST}")
            print(f"  {C.DIM}The following {len(failed_downloads)} URLs encountered terminal errors during processing:{C.RST}")
            for u in failed_downloads:
                print(f"  {C.DIM}- {u}{C.RST}")
            hr(C.RED)
            
    except KeyboardInterrupt:
        if 'ui_state' in locals():
            ui_state.is_active = False
        handle_interrupt(None, None)
    finally:
        if 'ui_state' in locals():
            ui_state.is_active = False
        sys.stdout.write("\033[?25h\n") # ensure cursor shown
        reset_colors()


if __name__ == "__main__":
    main()
