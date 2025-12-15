#!/usr/bin/env python3
"""
🎵 TikTok Downloader - by kwishtt
https://github.com/kwishtt

Usage:
    python3 ytdl.py              # Chạy với menu chọn format
    python3 ytdl.py list.txt     # Dùng file khác thay vì user.txt
"""

import json
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, 
        BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
    )
except ImportError:
    print("❌ Cần cài đặt rich: pip install rich")
    sys.exit(1)

# ========== KHỞI TẠO ==========
console = Console()

# Output folder chính
OUTPUT_FOLDER = "TikTok_Downloads"

# ========== CHỐNG BLOCK IP ==========
MIN_DELAY = 3
MAX_DELAY = 8
MAX_RETRIES = 3

# ========== SMART SKIP ==========
# Nếu user đã check trong vòng X giờ và không có video mới → skip
SKIP_HOURS = 2  # Skip nếu đã check trong 24h gần đây
CACHE_FILE = ".download_cache.json"


# ========== CACHE FUNCTIONS ==========
def load_cache() -> dict:
    """Load cache từ file"""
    cache_path = Path.cwd() / OUTPUT_FOLDER / CACHE_FILE
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    """Lưu cache ra file"""
    cache_path = Path.cwd() / OUTPUT_FOLDER / CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def should_skip_user(username: str, cache: dict) -> tuple[bool, str]:
    """
    Kiểm tra xem có nên skip user không.
    
    Returns:
        tuple: (should_skip, reason)
    """
    if username not in cache:
        return False, ""
    
    user_data = cache[username]
    last_check = datetime.fromisoformat(user_data.get("last_check", "2000-01-01"))
    hours_since = (datetime.now() - last_check).total_seconds() / 3600
    
    # Nếu check gần đây và lần trước không có video mới
    if hours_since < SKIP_HOURS and user_data.get("no_new_videos", False):
        return True, f"Đã check {hours_since:.1f}h trước, không có video mới"
    
    return False, ""


def update_cache(username: str, cache: dict, new_videos: int) -> None:
    """Cập nhật cache sau khi tải"""
    cache[username] = {
        "last_check": datetime.now().isoformat(),
        "no_new_videos": new_videos == 0,
        "total_videos": cache.get(username, {}).get("total_videos", 0) + new_videos
    }


# ========== KIỂM TRA DEPENDENCIES ==========
def check_deps() -> bool:
    """Kiểm tra yt-dlp và ffmpeg"""
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    
    if missing:
        console.print(Panel(
            f"[red]❌ Thiếu:[/red] [yellow]{', '.join(missing)}[/yellow]\n\n"
            f"[dim]Cài đặt:[/dim]\n"
            f"  yt-dlp: [cyan]pip install yt-dlp[/cyan]\n"
            f"  ffmpeg: [cyan]sudo apt install ffmpeg[/cyan]",
            title="⚠️ Thiếu Dependencies",
            border_style="red"
        ))
        return False
    return True


def extract_username(url: str) -> Optional[str]:
    """Trích xuất username từ URL TikTok"""
    match = re.search(r'tiktok\.com/@([^/?]+)', url)
    return match.group(1) if match else None


def random_delay() -> None:
    """Delay ngẫu nhiên để tránh bị rate limit"""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    console.print(f"  [dim]⏳ Chờ {delay:.1f}s...[/dim]")
    time.sleep(delay)


def scan_user_videos(url: str, use_cookies: bool = True) -> int:
    """
    Scan số video trong profile TikTok (không tải).
    
    Returns:
        int: Số video trong profile, -1 nếu lỗi
    """
    cmd = [
        "yt-dlp",
        "--flat-playlist",  # Chỉ lấy metadata, không tải
        "--print", "id",    # In ra ID của mỗi video
        "--no-warnings",
        "--quiet",
    ]
    
    if use_cookies:
        cmd.extend(["--cookies-from-browser", "chrome"])
    
    cmd.append(url)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # Timeout 60s cho scan
        )
        
        if result.returncode == 0:
            # Đếm số dòng (mỗi dòng là 1 video ID)
            video_ids = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            return len(video_ids)
        return -1
        
    except subprocess.TimeoutExpired:
        return -1
    except Exception:
        return -1


def count_downloaded_videos(username: str) -> int:
    """Đếm số video đã tải của user"""
    user_dir = Path.cwd() / OUTPUT_FOLDER / f"@{username}"
    if not user_dir.exists():
        return 0
    
    # Đếm cả trong thư mục gốc và subfolder videos
    count = len(list(user_dir.glob("*.mp4")))
    videos_dir = user_dir / "videos"
    if videos_dir.exists():
        count += len(list(videos_dir.glob("*.mp4")))
    
    return count


def download_user(url: str, fmt: str, use_cookies: bool = True) -> tuple[bool, dict, Path]:
    """
    Tải video/audio của 1 TikTok user.
    
    Returns:
        tuple: (success, stats, output_dir)
    """
    username = extract_username(url)
    if not username:
        console.print(f"[red]❌ Không thể lấy username từ: {url}[/red]")
        return False, {"mp4": 0, "mp3": 0}, Path.cwd()
    
    base_dir = Path.cwd() / OUTPUT_FOLDER / f"@{username}"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {"mp4": 0, "mp3": 0}
    
    # ===== TẢI MP4 =====
    if fmt in ("mp4", "both"):
        if fmt == "both":
            video_dir = base_dir / "videos"
        else:
            video_dir = base_dir
        video_dir.mkdir(parents=True, exist_ok=True)
        
        archive_file = base_dir / ".video_archive"
        before = len(list(video_dir.glob("*.mp4")))
        
        cmd = [
            "yt-dlp",
            "-f", "best[ext=mp4]/best",
            "-o", str(video_dir / "%(title).50s_%(id)s.%(ext)s"),
            "--download-archive", str(archive_file),
            "--restrict-filenames",
            "--sleep-requests", "1.5",
            "--sleep-interval", "2",
            "--max-sleep-interval", "5",
            "--retries", "5",
            "--fragment-retries", "5",
            "--no-warnings",
            "--quiet",
            "--progress",
        ]
        
        if use_cookies:
            cmd.extend(["--cookies-from-browser", "chrome"])
        
        cmd.append(url)
        
        for attempt in range(MAX_RETRIES):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                
                if "HTTP Error 429" in result.stderr or "rate limit" in result.stderr.lower():
                    console.print(f"  [yellow]⚠️ Rate limited! Chờ và thử lại... ({attempt + 1}/{MAX_RETRIES}) hoặc đổi mạng sang 3G/4G để tải [/yellow]")
                    time.sleep(30 * (attempt + 1))
                    continue
                
                break
            except subprocess.TimeoutExpired:
                console.print(f"  [yellow]⏱️ Timeout, thử lại... ({attempt + 1}/{MAX_RETRIES})[/yellow]")
                continue
            except Exception as e:
                console.print(f"  [red]❌ Lỗi: {e}[/red]")
                break
        
        stats["mp4"] = len(list(video_dir.glob("*.mp4"))) - before
    
    # ===== TẢI MP3 =====
    if fmt in ("mp3", "both"):
        if fmt == "both":
            audio_dir = base_dir / "audios"
        else:
            audio_dir = base_dir
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        archive_file = base_dir / ".audio_archive"
        before = len(list(audio_dir.glob("*.mp3")))
        
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", str(audio_dir / "%(title).50s_%(id)s.%(ext)s"),
            "--download-archive", str(archive_file),
            "--restrict-filenames",
            "--sleep-requests", "1.5",
            "--sleep-interval", "2",
            "--max-sleep-interval", "5",
            "--retries", "5",
            "--fragment-retries", "5",
            "--no-warnings",
            "--quiet",
            "--progress",
        ]
        
        if use_cookies:
            cmd.extend(["--cookies-from-browser", "chrome"])
        
        cmd.append(url)
        
        for attempt in range(MAX_RETRIES):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                
                if "HTTP Error 429" in result.stderr or "rate limit" in result.stderr.lower():
                    console.print(f"  [yellow]⚠️ Rate limited! Chờ thử lại... ({attempt + 1}/{MAX_RETRIES})[/yellow]")
                    time.sleep(30 * (attempt + 1))
                    continue
                
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception:
                break
        
        stats["mp3"] = len(list(audio_dir.glob("*.mp3"))) - before
    
    return True, stats, base_dir


def print_banner() -> None:
    """Hiển thị banner"""
    console.print(Panel(
        "[bold magenta]🎵 TikTok Downloader[/bold magenta]\n"
        "[dim]Make by kwishtt[/dim]\n",
        border_style="magenta"
    ))


def show_format_menu() -> str:
    """Hiển thị menu chọn format"""
    console.print("\n[bold]📦 Chọn định dạng tải:[/bold]\n")
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Option", style="cyan bold", width=4)
    table.add_column("Format", style="white")
    table.add_column("Mô tả", style="dim")
    
    table.add_row("[1]", "🎬 Video (MP4)", "Chỉ tải video")
    table.add_row("[2]", "🎵 Audio (MP3)", "Chỉ tải nhạc")
    table.add_row("[3]", "🎬🎵 Cả hai", "Tải video + nhạc")
    
    console.print(table)
    console.print()
    
    while True:
        choice = Prompt.ask(
            "[bold]Nhập lựa chọn[/bold]",
            choices=["1", "2", "3"],
            default="1"
        )
        
        format_map = {"1": "mp4", "2": "mp3", "3": "both"}
        return format_map[choice]


def print_final_summary(results: dict, skipped: list, fmt: str) -> None:
    """In thống kê ngắn gọn cuối cùng"""
    output_path = Path.cwd() / OUTPUT_FOLDER
    
    # Tính tổng từ kết quả
    total_new_mp4 = sum(stats["mp4"] for _, (_, stats, _) in results.items())
    total_new_mp3 = sum(stats["mp3"] for _, (_, stats, _) in results.items())
    
    # Đếm tổng file trong thư mục
    total_videos = len(list(output_path.rglob("*.mp4"))) if output_path.exists() else 0
    total_audios = len(list(output_path.rglob("*.mp3"))) if output_path.exists() else 0
    
    # Build thông báo
    new_items = []
    if fmt in ("mp4", "both"):
        new_items.append(f"[green]+{total_new_mp4} videos[/green]")
    if fmt in ("mp3", "both"):
        new_items.append(f"[yellow]+{total_new_mp3} audios[/yellow]")
    
    skip_text = f"\n[bold]-> Đã skip:[/bold] {len(skipped)} users (check gần đây)" if skipped else ""
    
    console.print(Panel(
        f"[bold green]Tải xuống hoàn tất[/bold green]\n\n"
        f"[bold]-> Mới tải:[/bold] {' | '.join(new_items)}\n"
        f"[bold]-> Đã xử lý:[/bold] {len(results)} users"
        f"{skip_text}\n"
        f"[bold]-> Tổng trong thư mục:[/bold] {total_videos} videos, {total_audios} audios\n\n"
        f"[bold]-> Lưu tại:[/bold]\n"
        f"[cyan]{output_path.resolve()}[/cyan]",
        title="🏁 Thống kê",
        border_style="green"
    ))


def main() -> None:
    """Main function"""
    print_banner()
    
    # Kiểm tra dependencies
    if not check_deps():
        sys.exit(1)
    
    # Lấy file input
    file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("user.txt")
    
    if not file_path.exists():
        console.print(f"\n[red]❌ File không tồn tại: {file_path}[/red]")
        console.print("[dim]Tạo file user.txt với mỗi dòng 1 link TikTok profile[/dim]")
        console.print("\n[dim]Ví dụ:[/dim]")
        console.print("  https://www.tiktok.com/@username1")
        console.print("  https://www.tiktok.com/@username2")
        sys.exit(1)
    
    # Đọc URLs
    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "tiktok.com" in line:
                urls.append(line)
    
    if not urls:
        console.print("\n[yellow]⚠️ Không có URL TikTok nào trong file![/yellow]")
        sys.exit(1)
    
    # Load cache
    cache = load_cache()
    
    # Hiển thị thông tin file
    console.print(f"\n[bold]📄 File:[/bold] {file_path.name}")
    console.print(f"[bold]👥 Số users:[/bold] {len(urls)}")
    
    # Menu chọn format
    fmt = show_format_menu()
    
    fmt_text = {"mp4": "🎬 Video (MP4)", "mp3": "🎵 Audio (MP3)", "both": "🎬🎵 Video + Audio"}
    console.print(f"\n[bold]✨ Đã chọn:[/bold] {fmt_text[fmt]}")
    console.print(f"[bold]📂 Lưu vào:[/bold] [cyan]{OUTPUT_FOLDER}/[/cyan]")
    
    # ===== SCAN TRƯỚC =====
    console.print("\n[bold]🔍 Đang scan số video...[/bold]\n")
    
    scan_results = []
    total_to_download = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        for url in urls:
            username = extract_username(url) or "unknown"
            task = progress.add_task(f"Scanning @{username}...", total=None)
            
            # Scan số video trong profile
            total_videos = scan_user_videos(url)
            downloaded = count_downloaded_videos(username)
            
            # Kiểm tra cache
            should_skip, skip_reason = should_skip_user(username, cache)
            
            if should_skip:
                status = "skip"
                need_download = 0
            elif total_videos == -1:
                # Scan lỗi nhưng vẫn cho tải
                status = "pending"
                need_download = 0  # Không biết trước
            else:
                status = "ok"
                need_download = max(0, total_videos - downloaded)
            
            scan_results.append({
                "username": username,
                "url": url,
                "total": total_videos,
                "downloaded": downloaded,
                "need": need_download,
                "status": status,
                "skip_reason": skip_reason
            })
            
            total_to_download += need_download
            progress.remove_task(task)
    
    # Hiển thị bảng tổng quan
    table = Table(title="-- Tổng quan --", show_header=True, header_style="bold cyan")
    table.add_column("User", style="cyan")
    table.add_column("Đã có", justify="right", style="green")
    table.add_column("Trạng thái", justify="center")
    
    pending_count = 0
    for r in scan_results:
        if r["status"] == "skip":
            status = "[dim]⏭️ Skip[/dim]"
        elif r["status"] == "pending":
            status = "[yellow]⏳ Chờ tải[/yellow]"
            pending_count += 1
        else:
            if r["need"] > 0:
                status = f"[green]📥 +{r['need']} mới[/green]"
            else:
                status = "[dim]✅ Đủ rồi[/dim]"
        
        table.add_row(
            f"@{r['username']}",
            str(r["downloaded"]),
            status
        )
    
    console.print(table)
    
    if pending_count > 0:
        console.print(f"\n[dim]💡 {pending_count} users không scan được, sẽ tải trực tiếp[/dim]")
    
    if total_to_download > 0:
        console.print(f"[bold]📥 Ước tính:[/bold] [yellow]+{total_to_download} videos mới[/yellow]")
    
    # Xác nhận
    console.print()
    confirm = Prompt.ask(
        "Bắt đầu tải?",
        choices=["y", "n"],
        default="y"
    )
    
    if confirm.lower() != "y":
        console.print("[yellow]Đã hủy.[/yellow]")
        sys.exit(0)
    
    console.print()
    
    # Tải từng user với progress bar
    results = {}
    skipped = []
    
    # Đếm số user cần tải (không skip)
    users_to_process = [r for r in scan_results if r["status"] != "skip"]
    total_users = len(users_to_process)
    
    # Tạo progress bar tổng thể
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=2
    ) as progress:
        
        # Task tổng thể
        overall_task = progress.add_task(
            f"[cyan]Tổng tiến trình[/cyan]", 
            total=total_users
        )
        
        processed = 0
        
        for idx, url in enumerate(urls, 1):
            username = extract_username(url) or "unknown"
            
            # Kiểm tra có nên skip không
            should_skip, reason = should_skip_user(username, cache)
            if should_skip:
                console.print(f"[dim]⏭️ @{username}: Skip - {reason}[/dim]")
                skipped.append(username)
                continue
            
            # Cập nhật mô tả task
            progress.update(overall_task, description=f"[cyan]@{username}[/cyan]")
            
            # Tải
            success, stats, output_dir = download_user(url, fmt)
            
            results[username] = (success, stats, output_dir)
            
            # Cập nhật cache
            total_new = stats["mp4"] + stats["mp3"]
            update_cache(username, cache, total_new)
            
            # Hiển thị kết quả ngắn gọn
            parts = []
            if fmt in ("mp4", "both") and stats["mp4"]:
                parts.append(f"+{stats['mp4']}v")
            if fmt in ("mp3", "both") and stats["mp3"]:
                parts.append(f"+{stats['mp3']}a")
            
            result_text = f"[green]{', '.join(parts)}[/green]" if parts else "[dim]0 mới[/dim]"
            console.print(f"  ✅ @{username}: {result_text}")
            
            # Cập nhật progress
            processed += 1
            progress.update(overall_task, completed=processed)
            
            # Delay giữa các user (trừ user cuối)
            if processed < total_users:
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)
    
    # Lưu cache
    save_cache(cache)
    
    # Tổng kết
    console.print()
    print_final_summary(results, skipped, fmt)


if __name__ == "__main__":
    main()
