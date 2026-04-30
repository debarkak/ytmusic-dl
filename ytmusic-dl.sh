#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  ytmusic-dl.sh
#  deps: yt-dlp, ffmpeg
# ─────────────────────────────────────────────

set -euo pipefail

# reset colors on exit, ctrl+c, or error
trap 'echo -ne "\033[0m"' EXIT
trap 'echo -ne "\033[0m"; exit 130' INT TERM

# ── colors ──────────────────────────────────
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
CYN='\033[0;36m'
BLD='\033[1m'
RST='\033[0m'

# ── concurrent fragments (tweak if needed) ───
FRAGMENTS=4

# ── dependency check ─────────────────────────
check_deps() {
    local missing=()
    command -v yt-dlp &>/dev/null || missing+=("yt-dlp")
    command -v ffmpeg &>/dev/null || missing+=("ffmpeg")
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}[error]${RST} missing deps: ${missing[*]}"
        echo -e "  just install them (pacman/apt/brew idc)"
        exit 1
    fi
}

# ── banner ───────────────────────────────────
banner() {
    echo -e "${CYN}"
    echo "  ╔═══════════════════════════════════╗"
    echo "  ║     ytmusic-dl                           ║"
    echo "  ║     rip anything off yt music            ║"
    echo "  ╚═══════════════════════════════════╝"
    echo -e "${RST}"
}

# ── prompt URL ───────────────────────────────
prompt_url() {
    if [[ -n "${1:-}" ]]; then
        URL="$1"
        echo -e "${BLD}url:${RST} ${CYN}${URL}${RST} ${RST}(from arg)"
        return
    fi

    echo -e "${BLD}drop the url:${RST}"
    read -rp "  → " URL
    if [[ -z "$URL" ]]; then
        echo -e "${RED}[error]${RST} bro u didn't paste anything"
        exit 1
    fi
}

# ── prompt format ────────────────────────────
prompt_format() {
    echo ""
    echo -e "${BLD}what format?${RST}"
    echo -e "  ${YLW}1${RST}) opus   — native yt audio, no re-encoding ${GRN}[just use this]${RST}"
    echo -e "  ${YLW}2${RST}) m4a    — AAC, decent compat"
    echo -e "  ${YLW}3${RST}) mp3    — works on everything, tiny quality hit"
    echo -e "  ${YLW}4${RST}) flac   — lossless wrapper around a lossy source lol"
    echo -e "  ${YLW}5${RST}) wav    — uncompressed, will eat your storage"
    echo ""
    read -rp "  [1-5, default 1]: " FMT_CHOICE

    case "${FMT_CHOICE:-1}" in
        1) AUDIO_FORMAT="opus" ;;
        2) AUDIO_FORMAT="m4a"  ;;
        3) AUDIO_FORMAT="mp3"  ;;
        4) AUDIO_FORMAT="flac" ;;
        5) AUDIO_FORMAT="wav"  ;;
        *)
            echo -e "${YLW}[warn]${RST} that's not valid, defaulting to opus"
            AUDIO_FORMAT="opus"
            ;;
    esac

    echo -e "  ${GRN}✓${RST} ${BLD}${AUDIO_FORMAT}${RST}"
}

# ── prompt directory ─────────────────────────
prompt_directory() {
    echo ""
    echo -e "${BLD}where to save?${RST}"
    echo -e "  ${YLW}1${RST}) right here (no folder, just dumps the files)"
    echo -e "  ${YLW}2${RST}) make a folder named after the album/thing ${GRN}[recommended]${RST}"
    echo ""
    read -rp "  [1/2, default 2]: " DIR_CHOICE

    case "${DIR_CHOICE:-2}" in
        1)
            OUTPUT_TEMPLATE="%(track_number,playlist_index)02d - %(title)s.%(ext)s"
            DIR_MODE="flat"
            ;;
        2)
            OUTPUT_TEMPLATE="%(album,playlist_title)s/%(track_number,playlist_index)02d - %(title)s.%(ext)s"
            DIR_MODE="album_folder"
            ;;
        *)
            echo -e "${YLW}[warn]${RST} that's not valid, going with album folder"
            OUTPUT_TEMPLATE="%(album,playlist_title)s/%(track_number,playlist_index)02d - %(title)s.%(ext)s"
            DIR_MODE="album_folder"
            ;;
    esac

    echo -e "  ${GRN}✓${RST} ${BLD}${DIR_MODE}${RST}"
}

# ── build format-specific flags ──────────────
build_format_flags() {
    EXTRA_FLAGS=()

    if [[ "$AUDIO_FORMAT" == "mp3" ]]; then
        # VBR q0 = best quality for mp3
        EXTRA_FLAGS+=("--audio-quality" "0")
        # jpeg embeds way more reliably in ID3 tags than png
        THUMB_CONVERT="jpg"
        THUMB_CODEC="mjpeg"
    else
        THUMB_CONVERT="png"
        THUMB_CODEC="png"
    fi
}

# ── run download ─────────────────────────────
run_download() {
    echo ""
    echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
    echo -e "${BLD}aight downloading${RST}"
    echo -e "  url    : ${URL}"
    echo -e "  format : ${AUDIO_FORMAT}"
    echo -e "  mode   : ${DIR_MODE}"
    echo -e "${CYN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
    echo ""

    yt-dlp \
        -f bestaudio \
        --extract-audio \
        --audio-format "${AUDIO_FORMAT}" \
        "${EXTRA_FLAGS[@]}" \
        -o "${OUTPUT_TEMPLATE}" \
        --embed-metadata \
        --embed-thumbnail \
        --convert-thumbnails "${THUMB_CONVERT}" \
        --ppa "ThumbnailsConvertor+ffmpeg_o:-c:v ${THUMB_CODEC} -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\"" \
        --parse-metadata "playlist_index:%(track_number)s" \
        --no-overwrites \
        --concurrent-fragments "${FRAGMENTS}" \
        "${URL}"

    echo ""
    echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
    echo -e "${GRN}${BLD}  ✓ done, enjoy${RST}"
    if [[ "$DIR_MODE" == "album_folder" ]]; then
        echo -e "  folder dropped in: ${BLD}$(pwd)${RST}"
    else
        echo -e "  files in: ${BLD}$(pwd)${RST}"
    fi
    echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
}

# ── main ─────────────────────────────────────
main() {
    banner
    check_deps
    prompt_url "${1:-}"
    prompt_format
    prompt_directory
    build_format_flags
    run_download
}

main "$@"