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

# Load environment variables
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

TEMP_DIR = os.getenv("TEMP_DIR")
DEST_DIR = os.getenv("DEST_DIR")

if not TEMP_DIR or not DEST_DIR:
    print("❌ Error: TEMP_DIR or DEST_DIR are not configured in the .env file.")
    sys.exit(1)

# Ensure TEMP_DIR exists
os.makedirs(TEMP_DIR, exist_ok=True)


def clean_text(text):
    """Removes content inside brackets and parenthesis from titles."""
    if not text:
        return ""
    cleaned = re.sub(r"[\(\[\{].*?[\)\]\}]", "", text)
    return " ".join(cleaned.split())


def sanitize_filename(name):
    """Removes illegal characters for file paths."""
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
        print("❌ Error: Missing YouTube URL.")
        print('Usage: nix run . -- "URL"')
        sys.exit(1)

    url = sys.argv[1]

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{TEMP_DIR}/%(title)s.%(ext)s",
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
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

    print("🔍 Extracting metadata...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"❌ Error extracting info: {e}")
            sys.exit(1)

        # Metadata extraction and cleaning
        raw_title = info.get("title", "Unknown Title")
        raw_artist = info.get("artist") or info.get("uploader", "Unknown Artist")
        raw_album = info.get("album") or raw_artist

        clean_title_str = clean_text(raw_title)

        print("\n--- Detected Metadata ---")
        print(f"Title:  {clean_title_str}")
        print(f"Artist: {raw_artist}")
        print(f"Album:  {raw_album}")
        print("-------------------------")

        # Interactive confirmation
        final_title = (
            input(f"Confirm Title [{clean_title_str}]: ").strip() or clean_title_str
        )
        final_artist = input(f"Confirm Artist [{raw_artist}]: ").strip() or raw_artist
        final_album = input(f"Confirm Album [{raw_album}]: ").strip() or raw_album

        print("\n⬇️  Downloading audio and metadata...")
        ydl.download([url])

    # Identify files
    files = os.listdir(TEMP_DIR)
    mp3_file = next((f for f in files if f.endswith(".mp3")), None)
    lrc_file = next((f for f in files if f.endswith(".lrc")), None)

    if not mp3_file:
        print("❌ Error: MP3 file not found after download.")
        sys.exit(1)

    mp3_path = os.path.join(TEMP_DIR, mp3_file)

    # Handle Lyrics
    if not lrc_file:
        print("🔎 No lyrics found on YouTube. Querying LRCLIB...")
        lyrics = fetch_external_lyrics(final_artist, final_title)
        if lyrics:
            lrc_path = os.path.join(TEMP_DIR, f"{sanitize_filename(final_title)}.lrc")
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write(lyrics)
            print("✅ Lyrics found and saved from LRCLIB!")
            lrc_file = os.path.basename(lrc_path)
        else:
            print("⚠️  No lyrics found on LRCLIB either.")
    else:
        print("✅ Lyrics downloaded from YouTube.")

    # Apply final tags with ffmpeg (preserving cover art)
    temp_out = os.path.join(TEMP_DIR, "temp_tagged.mp3")
    print("🏷️  Applying metadata tags and preserving cover art...")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            mp3_path,
            "-map",
            "0",
            "-c",
            "copy",
            "-id3v2_version",
            "3",
            "-metadata",
            f"title={final_title}",
            "-metadata",
            f"artist={final_artist}",
            "-metadata",
            f"album={final_album}",
            temp_out,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    os.replace(temp_out, mp3_path)

    # Move to final destination
    safe_artist = sanitize_filename(final_artist)
    safe_album = sanitize_filename(final_album)
    safe_title = sanitize_filename(final_title)

    final_dir = os.path.join(DEST_DIR, safe_artist, safe_album)
    os.makedirs(final_dir, exist_ok=True)

    final_mp3_path = os.path.join(final_dir, f"{safe_artist} - {safe_title}.mp3")
    shutil.move(mp3_path, final_mp3_path)
    print(f"🎵 Audio saved to: {final_mp3_path}")

    if lrc_file:
        lrc_path = os.path.join(TEMP_DIR, lrc_file)
        final_lrc_path = os.path.join(final_dir, f"{safe_artist} - {safe_title}.lrc")
        shutil.move(lrc_path, final_lrc_path)
        print(f"📝 Lyrics saved to: {final_lrc_path}")

    # Cleanup
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print("✨ Done!")


if __name__ == "__main__":
    main()
