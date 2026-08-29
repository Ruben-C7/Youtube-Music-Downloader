# YT Music Downloader

A robust tool to download audio from YouTube and YouTube Music with perfect metadata formatting and synchronized lyrics support. Designed specifically for media servers like Navidrome and Jellyfin.

## ✨ Features

- **Nix-Powered:** Zero dependency conflicts. Packages like `yt-dlp` and `ffmpeg` are sandboxed and fully reproducible.
- **Smart Metadata:** Automatically cleans titles (removes tags like "(Official Video)", "[HD]", etc.) using Regex.
- **Advanced Lyrics Support:** Downloads and converts YouTube subtitles to `.lrc` format. If not available on YouTube, it automatically falls back to the **LRCLIB** database to find perfect synchronized lyrics.
- **Organized Structure:** Automatically moves and renames files into `Artist/Album/Artist - Title.mp3`.
- **Customizable:** Environment variables for destination folders are safely stored in a `.env` file.

## 🚀 Installation & Setup

1. **Clone the repository:**

   ```bash
   git clone [https://github.com/Ruben-C7/yt-music-downloader.git](https://github.com/Ruben-C7/yt-music-downloader.git)
   cd yt-music-downloader
   ```

2. **Configure Environment Variables:**
   Copy the template and set your destination folder for your media server:

```bash
cp .env.template .env
nano .env

```

3. **Initialize Nix Flake (First run only):**
   Generates the lockfile to ensure reproducible dependencies.

```bash
nix flake update

```

## 🎵 Usage

Run the tool using Nix, passing the YouTube URL as an argument. **Important:** Always wrap the URL in quotes to prevent shell issues with special characters like `&`.

```bash
nix run . -- "[https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=)..."

```

The script will present the detected metadata and lyrics status, allowing you to interactively confirm or edit the tags before the download starts.

## 📜 License

This project is licensed under the MIT License.
