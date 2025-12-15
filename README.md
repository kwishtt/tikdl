# 🎵 TikTok Downloader

A simple and powerful CLI tool to batch download TikTok videos and audio.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 🇻🇳 **Vietnamese version**: [README_VI.md](README_VI.md)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📦 **Batch Download** | Download from multiple TikTok profiles at once |
| 🎬 **Video (MP4)** | Download highest quality videos |
| 🎵 **Audio (MP3)** | Extract audio only |
| 📁 **Auto-organize** | Files organized by `@username` folders |
| 🧠 **Smart Skip** | Skip recently checked users (no new videos) |
| 🛡️ **Anti-block** | Built-in delays and retry mechanism |
| 📊 **Progress Bar** | Beautiful progress tracking with ETA |
| 🍪 **Cookie Support** | Uses browser cookies to avoid rate limits |

---

## 📋 Requirements

- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (for audio extraction)
- Chrome/Edge browser (for cookies)

---

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/kwishtt/tiktok-dl.git
cd tiktok-dl
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Install yt-dlp and ffmpeg
```bash
# yt-dlp
pip install yt-dlp

# ffmpeg (Ubuntu/Debian)
sudo apt install ffmpeg

# ffmpeg (macOS)
brew install ffmpeg

# ffmpeg (Windows)
# Download from https://ffmpeg.org/download.html
```

---

## 📖 Usage

### 1. Create a user list file
Create `user.txt` with TikTok profile URLs (one per line):
```
https://www.tiktok.com/@username1
https://www.tiktok.com/@username2
https://www.tiktok.com/@username3
```

### 2. Run the downloader
```bash
python3 ytdl.py
```

### 3. Select format
```
📦 Choose download format:

  [1]  🎬 Video (MP4)    Video only
  [2]  🎵 Audio (MP3)    Audio only
  [3]  🎬🎵 Both         Video + Audio

Enter choice [1/2/3] (1): 
```

### 4. Confirm and download
The tool will:
1. Scan all users
2. Show a summary table
3. Download with progress bar
4. Save files to `TikTok_Downloads/@username/`

---

## 📁 Output Structure

```
TikTok_Downloads/
├── @username1/
│   ├── video_title_abc123.mp4
│   ├── video_title_def456.mp4
│   └── .video_archive          # (hidden) tracks downloaded videos
├── @username2/
│   └── ...
└── .download_cache.json        # (hidden) smart skip cache
```

---

## ⚙️ Configuration

Edit these variables in `ytdl.py`:

```python
# Anti-block settings
MIN_DELAY = 3          # Min delay between users (seconds)
MAX_DELAY = 8          # Max delay between users (seconds)

# Smart skip
SKIP_HOURS = 24        # Skip if checked within X hours
```

---

## 🛡️ Anti-Block Features

| Feature | Description |
|---------|-------------|
| Random delay | 3-8s random delay between users |
| Sleep requests | 1.5s delay between HTTP requests |
| Sleep interval | 2-5s random delay between videos |
| Retry mechanism | Auto-retry on failure (max 5 times) |
| Exponential backoff | Increasing wait time on rate limit (429) |
| Browser cookies | Uses Chrome cookies for authentication |

---

## 📊 Smart Skip

The tool remembers when each user was last checked. If:
- User was checked within 24 hours, AND
- No new videos were found last time

→ User will be **skipped** to save time.

To force re-download all users, delete:
```bash
rm TikTok_Downloads/.download_cache.json
```

---

## 🔧 Troubleshooting

### "Rate limited" error
- Switch to mobile data (3G/4G)
- Wait 10-30 minutes
- Use a VPN

### Videos not downloading
- Update yt-dlp: `pip install -U yt-dlp`
- Check if profile is private
- Try with different browser cookies

### ffmpeg not found
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Check installation
ffmpeg -version
```

---

## 📄 License

MIT License - feel free to use and modify!

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

## ⭐ Star History

If you find this useful, please give it a ⭐!

---

Made with ❤️ by [kwishtt](https://github.com/kwishtt)
