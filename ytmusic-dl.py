#!/usr/bin/env python3
# ─────────────────────────────────────────────
#  ytmusic-dl.py
#  deps: yt-dlp, ffmpeg
# ─────────────────────────────────────────────

import sys
import os
import re
import signal
import shutil
import subprocess
import time
import platform
from pathlib import Path


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
    BLD = "\033[1m"
    DIM = "\033[2m"
    RST = "\033[0m"


# disable colors if not a tty (piping, redirects, etc.)
if not sys.stdout.isatty():
    for attr in ("RED", "GRN", "YLW", "CYN", "MGN", "BLD", "DIM", "RST"):
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
    print()

    try:
        choice = input("    [1/2, default 2]: ").strip()
    except EOFError:
        choice = ""

    if not choice:
        choice = "2"

    # yt-dlp handles path separators internally, so / works on all platforms
    if choice == "1":
        template = "%(track_number,playlist_index)02d - %(title)s.%(ext)s"
        mode = "flat"
    elif choice == "2":
        template = "%(album,playlist_title)s/%(track_number,playlist_index)02d - %(title)s.%(ext)s"
        mode = "album_folder"
    else:
        print(f"    {C.YLW}!{C.RST} {C.DIM}not valid, going with album folder{C.RST}")
        template = "%(album,playlist_title)s/%(track_number,playlist_index)02d - %(title)s.%(ext)s"
        mode = "album_folder"

    print(f"  {C.GRN}✓{C.RST} {C.BLD}{mode}{C.RST}")
    return template, mode


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


# ── run download ────────────────────────────
def run_download(url, audio_format, output_template, dir_mode):
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
    print(f"  {C.DIM}├ skip existing: yes{C.RST}")
    print(f"  {C.DIM}└ concurrent fragments: {FRAGMENTS}{C.RST}")
    print()

    # build the yt-dlp command
    # the crop filter uses single quotes which work on all platforms
    # when passed as a single argument in a list (not shell-expanded)
    crop_filter = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"
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
        "--concurrent-fragments", str(FRAGMENTS),
        url,
    ]

    start_time = time.time()

    # run yt-dlp
    try:
        result = subprocess.run(cmd)
        exit_code = result.returncode
    except FileNotFoundError:
        # yt-dlp binary not found (shouldn't happen after dep check, but just in case)
        print(f"\n  {C.RED}✗{C.RST} couldn't run yt-dlp, is it in your PATH?")
        sys.exit(1)

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
    if dir_mode == "album_folder":
        print(f"  {C.DIM}folder:{C.RST} {C.BLD}{Path.cwd()}{C.RST}")
    else:
        print(f"  {C.DIM}files:{C.RST}  {C.BLD}{Path.cwd()}{C.RST}")
    hr(C.GRN)


# ── main ────────────────────────────────────
def main():
    try:
        banner()
        check_deps()

        # grab url from args if provided
        arg_url = sys.argv[1] if len(sys.argv) > 1 else None
        url = prompt_url(arg_url)

        audio_format = prompt_format()
        output_template, dir_mode = prompt_directory()

        run_download(url, audio_format, output_template, dir_mode)
    except KeyboardInterrupt:
        handle_interrupt(None, None)
    finally:
        reset_colors()


if __name__ == "__main__":
    main()
