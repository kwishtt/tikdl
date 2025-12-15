<div align="center">

# TikTok Downloader

**A simple and powerful CLI tool to batch download TikTok videos and audio.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![yt-dlp](https://img.shields.io/badge/Powered%20by-yt--dlp-red?style=for-the-badge)](https://github.com/yt-dlp/yt-dlp)

[English](#features) | [Tiếng Việt](docs/README_VI.md)

</div>

---

## Features

<table>
<tr>
<td><img src="https://img.shields.io/badge/-Batch%20Download-blue?style=flat-square" alt="Batch"/></td>
<td>Download from multiple TikTok profiles at once</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Video%20MP4-red?style=flat-square" alt="Video"/></td>
<td>Download highest quality videos</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Audio%20MP3-orange?style=flat-square" alt="Audio"/></td>
<td>Extract audio only</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Auto%20Organize-purple?style=flat-square" alt="Organize"/></td>
<td>Files organized by <code>@username</code> folders</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Smart%20Skip-green?style=flat-square" alt="Skip"/></td>
<td>Skip recently checked users (no new videos)</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Anti%20Block-yellow?style=flat-square" alt="Anti-block"/></td>
<td>Built-in delays and retry mechanism</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Progress%20Bar-cyan?style=flat-square" alt="Progress"/></td>
<td>Beautiful progress tracking with ETA</td>
</tr>
<tr>
<td><img src="https://img.shields.io/badge/-Cookie%20Support-pink?style=flat-square" alt="Cookie"/></td>
<td>Uses browser cookies to avoid rate limits</td>
</tr>
</table>

---

## Requirements

- Python 3.8+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (for audio extraction)
- Chrome/Edge browser (for cookies)

---

## Installation

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

## Usage

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
Choose download format:

  [1]  Video (MP4)    Video only
  [2]  Audio (MP3)    Audio only
  [3]  Both           Video + Audio

Enter choice [1/2/3] (1): 
```

### 4. Confirm and download
The tool will:
1. Scan all users
2. Show a summary table
3. Download with progress bar
4. Save files to `TikTok_Downloads/@username/`

---

## Output Structure

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

## Configuration

Edit these variables in `ytdl.py`:

```python
# Anti-block settings
MIN_DELAY = 3          # Min delay between users (seconds)
MAX_DELAY = 8          # Max delay between users (seconds)

# Smart skip
SKIP_HOURS = 24        # Skip if checked within X hours
```

---

## Anti-Block Features

| Feature | Description |
|---------|-------------|
| Random delay | 3-8s random delay between users |
| Sleep requests | 1.5s delay between HTTP requests |
| Sleep interval | 2-5s random delay between videos |
| Retry mechanism | Auto-retry on failure (max 5 times) |
| Exponential backoff | Increasing wait time on rate limit (429) |
| Browser cookies | Uses Chrome cookies for authentication |

---

## Smart Skip

The tool remembers when each user was last checked. If:
- User was checked within 24 hours, AND
- No new videos were found last time

The user will be **skipped** to save time.

To force re-download all users, delete:
```bash
rm TikTok_Downloads/.download_cache.json
```

---

## Troubleshooting

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

## License

MIT License - feel free to use and modify!

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

<div align="center">

**If you find this useful, please give it a star!**

[![Star](https://img.shields.io/github/stars/kwishtt/tiktok-dl?style=social)](https://github.com/kwishtt/tiktok-dl)

Made with love by [kwishtt](https://github.com/kwishtt)

</div>
