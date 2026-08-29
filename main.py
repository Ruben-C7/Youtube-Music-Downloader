import os
import sys
import shutil
import re
import subprocess
import json
import urllib.request
import urllib.parse
import yt_dlp
from dotenv import load_dotenv

# Force reading .env from the current working directory
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

TEMP_DIR = os.getenv("TEMP_DIR")
DEST_DIR = os.getenv("DEST_DIR")

if not TEMP_DIR or not DEST_DIR:
    print("❌ Error: TEMP_DIR or DEST_DIR are not configured.")
    print("Copy .env.template to .env and adjust the paths.")
    sys.exit(1)


def clean_text(text):
    """Removes unwanted tags like (Official Video), [HD], etc."""
    if not text:
        return ""
    cleaned = re.sub(r"[\(\[\{].*?[\)\]\}]", "", text)
    return " ".join(cleaned.split())


def sanitize_filename(name):
    """Replaces invalid characters for safe folder and file naming."""
    if not name:
        return "Unknown"
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def fetch_external_lyrics(artist, title):
    """Queries LRCLIB API for lyrics. Tries full artist name, then falls back to primary artist."""

    # Attempt 1: Full artist name (e.g., "Artist A, Artist B")
    try:
        query = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
        url = f"https://lrclib.net/api/get?{query}"

        req = urllib.request.Request(
            url, headers={"User-Agent": "YT-Music-Downloader (Navidrome)"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("syncedLyrics")
    except Exception:
        pass  # If it fails, move silently to the second attempt

    # Attempt 2: Primary Artist only (splits by comma, &, feat, ft, with)
    primary_artist = re.split(r"(?i)[,&]| feat\. | ft\. | with ", artist)[0].strip()

    # Only perform a new search if the isolated name is actually different from the original
    if primary_artist and primary_artist != artist:
        try:
            query = urllib.parse.urlencode(
                {"artist_name": primary_artist, "track_name": title}
            )
            url = f"https://lrclib.net/api/get?{query}"

            req = urllib.request.Request(
                url, headers={"User-Agent": "YT-Music-Downloader (Navidrome)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    return data.get("syncedLyrics")
        except Exception:
            pass

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: nix run . -- <YouTube URL>")
        sys.exit(1)

    url = sys.argv[1]

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)

    print("🔍 Analyzing YouTube video...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{TEMP_DIR}/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            {"key": "EmbedThumbnail"},
            {"key": "FFmpegMetadata"},
        ],
        "writesubtitles": True,
        "subtitleslangs": ["all", "-live_chat"],
        "subtitlesformat": "lrc",
        "parse_metadata": "title:%(artist)s - %(title)s",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        raw_title = info.get("title", "Unknown Title")
        raw_artist = info.get("artist") or info.get("uploader") or "Unknown Artist"
        raw_album = info.get("album") or "Unknown Album"

        cleaned_title = clean_text(raw_title)
        if " - " in cleaned_title and info.get("artist") is None:
            parts = cleaned_title.split(" - ", 1)
            raw_artist = parts[0].strip()
            cleaned_title = parts[1].strip()

        has_cover = bool(info.get("thumbnail") or info.get("thumbnails"))
        has_yt_lyrics = bool(info.get("subtitles") or info.get("automatic_captions"))

        external_lyrics_data = None

        cover_status = "✅ Yes" if has_cover else "❌ No"

        # Pre-check lyrics availability
        if has_yt_lyrics:
            lyrics_status = "✅ Yes (YouTube)"
        else:
            external_lyrics_data = fetch_external_lyrics(raw_artist, cleaned_title)
            if external_lyrics_data:
                lyrics_status = "✅ Yes (LRCLIB)"
            else:
                lyrics_status = "❌ No (Not found anywhere)"

        print("\n=== 🎵 Detected Metadata ===")
        print(f"Original Title : {raw_title}")
        print(f"Cleaned Title  : \033[92m{cleaned_title}\033[0m")
        print(f"Artist         : \033[96m{raw_artist}\033[0m")
        print(f"Album          : \033[93m{raw_album}\033[0m")
        print(f"Cover Art      : {cover_status}")
        print(f"Lyrics         : {lyrics_status}")
        print("==============================\n")

        edit = input("Do you want to change the metadata? (y/N): ").strip().lower()

        final_title = cleaned_title
        final_artist = raw_artist
        final_album = raw_album

        if edit == "y":
            t = input(f"Title [{cleaned_title}]: ").strip()
            a = input(f"Artist [{raw_artist}]: ").strip()
            al = input(f"Album [{raw_album}]: ").strip()

            final_title = t if t else cleaned_title
            final_artist = a if a else raw_artist
            final_album = al if al else raw_album

            # If metadata changed and we didn't have lyrics, try searching LRCLIB again
            if not has_yt_lyrics and not external_lyrics_data:
                print("\n⏳ Re-checking external lyrics with updated metadata...")
                external_lyrics_data = fetch_external_lyrics(final_artist, final_title)
                if external_lyrics_data:
                    print("✅ Found lyrics with the new metadata!")

        print("\n⬇️ Downloading music and cover...")
        ydl.download([url])

    files = os.listdir(TEMP_DIR)
    mp3_file = next((f for f in files if f.endswith(".mp3")), None)

    if not mp3_file:
        print("❌ Error: MP3 file not found.")
        sys.exit(1)

    mp3_path = os.path.join(TEMP_DIR, mp3_file)
    print("📝 Applying final tags and cover...")
    temp_out = os.path.join(TEMP_DIR, "temp_tagged.mp3")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            mp3_path,
            "-metadata",
            f"title={final_title}",
            "-metadata",
            f"artist={final_artist}",
            "-metadata",
            f"album={final_album}",
            "-c",
            "copy",
            temp_out,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.replace(temp_out, mp3_path)

    safe_artist = sanitize_filename(final_artist)
    safe_album = sanitize_filename(final_album)
    safe_title = sanitize_filename(final_title)

    final_dir = os.path.join(DEST_DIR, safe_artist, safe_album)
    print(f"\n📂 Moving to Navidrome: {final_dir}")
    os.makedirs(final_dir, exist_ok=True)

    new_mp3_name = f"{safe_artist} - {safe_title}.mp3"
    shutil.move(mp3_path, os.path.join(final_dir, new_mp3_name))

    # Handle lyrics saving
    final_lrc_path = os.path.join(final_dir, f"{safe_artist} - {safe_title}.lrc")
    lrc_file = next((f for f in files if f.endswith(".lrc")), None)

    if lrc_file:
        shutil.move(os.path.join(TEMP_DIR, lrc_file), final_lrc_path)
        print("✅ Using lyrics found directly on YouTube.")
    elif external_lyrics_data:
        # Save the lyrics we held in memory from LRCLIB
        with open(final_lrc_path, "w", encoding="utf-8") as f:
            f.write(external_lyrics_data)
        print("✅ Synced lyrics saved from LRCLIB.")
    else:
        print("❌ No synchronized lyrics available.")

    shutil.rmtree(TEMP_DIR)
    print("✅ Finished successfully!")


if __name__ == "__main__":
    main()
