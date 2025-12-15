#!/usr/bin/env python3
"""
TikTok Auto Poster - Đăng video TikTok tự động theo lịch

Khung giờ:
- Sáng: 7h-9h
- Trưa: 11h-15h  
- Tối: 20h-23h

Mỗi khung giờ đăng 1 video, random thời gian để tránh detect bot.
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
except ImportError:
    print("Cần cài đặt: pip install playwright rich")
    print("Sau đó chạy: playwright install chromium")
    sys.exit(1)

# ========== CONFIG ==========
console = Console()

# Thư mục chứa video (output của ytdl.py)
VIDEO_SOURCE = Path(__file__).parent / "TikTok_Downloads"

# Files config
ACCOUNTS_FILE = Path(__file__).parent / "accounts.txt"
HASHTAGS_FILE = Path(__file__).parent / "hashtags.txt"
POSTED_FILE = Path(__file__).parent / "posted_videos.json"
ACCOUNT_FOLDER_MAP = Path(__file__).parent / "account_folders.json"

# Khung giờ đăng (giờ bắt đầu, giờ kết thúc)
SCHEDULE = {
    "morning": (7, 9),    # 7:00 - 9:00
    "noon": (11, 15),     # 11:00 - 15:00
    "night": (20, 23)     # 20:00 - 23:00
}


# ========== UTILITY FUNCTIONS ==========
def load_json(file_path: Path) -> dict:
    """Load JSON file"""
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(file_path: Path, data: dict) -> None:
    """Save JSON file"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_accounts() -> list[dict]:
    """Load accounts từ file accounts.txt"""
    accounts = []
    if not ACCOUNTS_FILE.exists():
        console.print(f"[red]File không tồn tại: {ACCOUNTS_FILE}[/red]")
        return accounts
    
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                parts = line.split(":", 1)
                accounts.append({
                    "email": parts[0].strip(),
                    "password": parts[1].strip()
                })
    
    return accounts


def load_hashtags() -> list[str]:
    """Load hashtags từ file"""
    hashtags = []
    if not HASHTAGS_FILE.exists():
        return hashtags
    
    with open(HASHTAGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Thêm # nếu chưa có
                if not line.startswith("#"):
                    line = "#" + line
                hashtags.append(line)
    
    return hashtags


def get_account_folder_map() -> dict:
    """Lấy mapping account -> folder"""
    return load_json(ACCOUNT_FOLDER_MAP)


def save_account_folder_map(mapping: dict) -> None:
    """Lưu mapping account -> folder"""
    save_json(ACCOUNT_FOLDER_MAP, mapping)


def get_posted_videos() -> dict:
    """Lấy danh sách video đã đăng"""
    return load_json(POSTED_FILE)


def mark_video_posted(account_email: str, video_path: str) -> None:
    """Đánh dấu video đã đăng"""
    posted = get_posted_videos()
    if account_email not in posted:
        posted[account_email] = []
    
    posted[account_email].append({
        "video": video_path,
        "posted_at": datetime.now().isoformat()
    })
    
    save_json(POSTED_FILE, posted)


def get_available_folders() -> list[str]:
    """Lấy danh sách folders có video"""
    if not VIDEO_SOURCE.exists():
        return []
    
    folders = []
    for item in VIDEO_SOURCE.iterdir():
        if item.is_dir() and item.name.startswith("@"):
            # Kiểm tra có video không
            videos = list(item.glob("*.mp4"))
            if videos:
                folders.append(item.name)
    
    return folders


def assign_folder_to_account(account_email: str) -> Optional[str]:
    """Gán folder cho account (nếu chưa có)"""
    mapping = get_account_folder_map()
    
    # Nếu account đã có folder
    if account_email in mapping:
        return mapping[account_email]
    
    # Lấy folders đã được gán
    assigned_folders = set(mapping.values())
    
    # Tìm folder chưa được gán
    available = get_available_folders()
    for folder in available:
        if folder not in assigned_folders:
            mapping[account_email] = folder
            save_account_folder_map(mapping)
            return folder
    
    return None


def get_next_video(account_email: str, folder: str) -> Optional[Path]:
    """Lấy video tiếp theo chưa đăng"""
    posted = get_posted_videos()
    posted_videos = [p["video"] for p in posted.get(account_email, [])]
    
    folder_path = VIDEO_SOURCE / folder
    if not folder_path.exists():
        return None
    
    # Lấy tất cả video trong folder
    all_videos = list(folder_path.glob("*.mp4"))
    
    # Lọc video chưa đăng
    for video in sorted(all_videos):
        if str(video) not in posted_videos:
            return video
    
    return None


def filename_to_caption(filename: str) -> str:
    """Chuyển tên file thành caption"""
    # Bỏ extension và ID
    name = Path(filename).stem
    
    # Bỏ phần ID cuối (thường là _abc123)
    name = re.sub(r'_[a-zA-Z0-9]{6,}$', '', name)
    
    # Thay _ bằng space
    name = name.replace("_", " ")
    
    # Capitalize
    name = name.strip()
    
    return name


def get_random_hashtags(count: int = 3) -> str:
    """Lấy random hashtags"""
    hashtags = load_hashtags()
    if not hashtags:
        return ""
    
    count = min(count, len(hashtags))
    selected = random.sample(hashtags, random.randint(2, count))
    return " ".join(selected)


def get_current_slot() -> Optional[str]:
    """Xác định khung giờ hiện tại"""
    hour = datetime.now().hour
    
    for slot_name, (start, end) in SCHEDULE.items():
        if start <= hour < end:
            return slot_name
    
    return None


def get_next_slot_time() -> tuple[str, datetime]:
    """Lấy thời gian random trong khung giờ tiếp theo"""
    now = datetime.now()
    hour = now.hour
    
    # Xác định khung giờ tiếp theo
    if hour < 7:
        slot = "morning"
        base_date = now.date()
    elif hour < 11:
        slot = "noon"
        base_date = now.date()
    elif hour < 20:
        slot = "night"
        base_date = now.date()
    else:
        slot = "morning"
        base_date = now.date() + timedelta(days=1)
    
    # Random thời gian trong khung
    start_hour, end_hour = SCHEDULE[slot]
    random_hour = random.randint(start_hour, end_hour - 1)
    random_minute = random.randint(0, 59)
    
    next_time = datetime.combine(base_date, datetime.min.time())
    next_time = next_time.replace(hour=random_hour, minute=random_minute)
    
    return slot, next_time


# ========== TIKTOK AUTOMATION ==========
def login_tiktok(page, email: str, password: str) -> bool:
    """Đăng nhập TikTok"""
    try:
        console.print(f"[cyan]Đang đăng nhập {email}...[/cyan]")
        
        # Vào trang login
        page.goto("https://www.tiktok.com/login/phone-or-email/email")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Nhập email
        email_input = page.locator('input[name="username"]')
        email_input.fill(email)
        time.sleep(0.5)
        
        # Nhập password
        password_input = page.locator('input[type="password"]')
        password_input.fill(password)
        time.sleep(0.5)
        
        # Click login
        login_btn = page.locator('button[type="submit"]')
        login_btn.click()
        
        # Chờ đăng nhập
        time.sleep(5)
        
        # Kiểm tra có captcha không
        if "captcha" in page.url.lower() or page.locator("text=Verify").count() > 0:
            console.print("[yellow]Cần xác thực CAPTCHA - Vui lòng giải thủ công...[/yellow]")
            input("Nhấn Enter sau khi giải xong CAPTCHA...")
        
        # Kiểm tra đăng nhập thành công
        page.wait_for_url("**/foryou**", timeout=30000)
        console.print(f"[green]Đăng nhập thành công: {email}[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Lỗi đăng nhập: {e}[/red]")
        return False


def upload_video(page, video_path: Path, caption: str) -> bool:
    """Upload video lên TikTok"""
    try:
        console.print(f"[cyan]Đang upload: {video_path.name}[/cyan]")
        console.print(f"[dim]Caption: {caption}[/dim]")
        
        # Vào trang upload
        page.goto("https://www.tiktok.com/upload")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Upload file
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(video_path))
        
        # Chờ upload xong
        console.print("[dim]Đang upload video...[/dim]")
        time.sleep(10)  # Tùy kích thước video
        
        # Nhập caption
        caption_editor = page.locator('[data-contents="true"]').first
        caption_editor.click()
        caption_editor.fill(caption)
        time.sleep(1)
        
        # Click Post
        post_btn = page.locator('button:has-text("Post")')
        if post_btn.count() > 0:
            post_btn.click()
            console.print("[dim]Đang đăng...[/dim]")
            time.sleep(10)
            
            console.print(f"[green]Đăng thành công: {video_path.name}[/green]")
            return True
        else:
            console.print("[red]Không tìm thấy nút Post[/red]")
            return False
        
    except Exception as e:
        console.print(f"[red]Lỗi upload: {e}[/red]")
        return False


def post_video_for_account(account: dict) -> bool:
    """Đăng video cho 1 account"""
    email = account["email"]
    password = account["password"]
    
    # Gán folder cho account
    folder = assign_folder_to_account(email)
    if not folder:
        console.print(f"[yellow]Không còn folder trống cho {email}[/yellow]")
        return False
    
    console.print(f"[cyan]Account: {email} -> Folder: {folder}[/cyan]")
    
    # Lấy video tiếp theo
    video = get_next_video(email, folder)
    if not video:
        console.print(f"[yellow]Hết video để đăng cho {email}[/yellow]")
        return False
    
    # Tạo caption
    caption = filename_to_caption(video.name)
    hashtags = get_random_hashtags(3)
    full_caption = f"{caption} {hashtags}".strip()
    
    # Thực hiện đăng
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False để debug
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Đăng nhập
            if not login_tiktok(page, email, password):
                return False
            
            # Upload video
            if upload_video(page, video, full_caption):
                mark_video_posted(email, str(video))
                return True
            
            return False
            
        finally:
            browser.close()


# ========== SCHEDULER ==========
def run_scheduler():
    """Chạy scheduler tự động"""
    console.print(Panel(
        "[bold magenta]TikTok Auto Poster[/bold magenta]\n"
        "[dim]Scheduler mode - Chạy liên tục[/dim]",
        border_style="magenta"
    ))
    
    accounts = load_accounts()
    if not accounts:
        console.print("[red]Không có account nào trong accounts.txt[/red]")
        return
    
    console.print(f"[bold]Accounts:[/bold] {len(accounts)}")
    console.print(f"[bold]Video source:[/bold] {VIDEO_SOURCE}")
    
    # Hiển thị schedule
    console.print("\n[bold]Khung giờ đăng:[/bold]")
    console.print("  Sáng: 7:00 - 9:00")
    console.print("  Trưa: 11:00 - 15:00")
    console.print("  Tối: 20:00 - 23:00")
    
    posted_today = {slot: False for slot in SCHEDULE.keys()}
    
    while True:
        current_slot = get_current_slot()
        now = datetime.now()
        
        if current_slot and not posted_today[current_slot]:
            console.print(f"\n[green]Đến giờ đăng ({current_slot})![/green]")
            
            # Đăng cho từng account
            for account in accounts:
                try:
                    post_video_for_account(account)
                    # Random delay giữa các account
                    delay = random.randint(60, 180)
                    console.print(f"[dim]Chờ {delay}s trước account tiếp theo...[/dim]")
                    time.sleep(delay)
                except Exception as e:
                    console.print(f"[red]Lỗi: {e}[/red]")
            
            posted_today[current_slot] = True
            console.print(f"[green]Hoàn thành slot {current_slot}[/green]")
        
        # Reset posted_today vào 0h
        if now.hour == 0 and now.minute < 5:
            posted_today = {slot: False for slot in SCHEDULE.keys()}
        
        # Hiển thị next slot
        next_slot, next_time = get_next_slot_time()
        wait_seconds = (next_time - now).total_seconds()
        
        if wait_seconds > 0:
            console.print(f"[dim]Next: {next_slot} @ {next_time.strftime('%H:%M')} (chờ {int(wait_seconds/60)} phút)[/dim]")
        
        # Sleep 5 phút rồi check lại
        time.sleep(300)


def run_once():
    """Chạy đăng 1 lần cho tất cả accounts"""
    console.print(Panel(
        "[bold magenta]TikTok Auto Poster[/bold magenta]\n"
        "[dim]One-time mode - Đăng ngay[/dim]",
        border_style="magenta"
    ))
    
    accounts = load_accounts()
    if not accounts:
        console.print("[red]Không có account nào trong accounts.txt[/red]")
        return
    
    console.print(f"[bold]Accounts:[/bold] {len(accounts)}")
    
    for account in accounts:
        try:
            post_video_for_account(account)
        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/red]")
        
        # Delay giữa accounts
        if account != accounts[-1]:
            delay = random.randint(60, 180)
            console.print(f"[dim]Chờ {delay}s...[/dim]")
            time.sleep(delay)
    
    console.print("[green]Hoàn thành![/green]")


def show_status():
    """Hiển thị trạng thái"""
    console.print(Panel(
        "[bold magenta]TikTok Auto Poster - Status[/bold magenta]",
        border_style="magenta"
    ))
    
    # Accounts
    accounts = load_accounts()
    console.print(f"\n[bold]Accounts ({len(accounts)}):[/bold]")
    for acc in accounts:
        console.print(f"  - {acc['email']}")
    
    # Folder mapping
    mapping = get_account_folder_map()
    console.print(f"\n[bold]Account -> Folder mapping:[/bold]")
    for email, folder in mapping.items():
        videos_left = 0
        folder_path = VIDEO_SOURCE / folder
        if folder_path.exists():
            posted = get_posted_videos()
            posted_videos = [p["video"] for p in posted.get(email, [])]
            all_videos = list(folder_path.glob("*.mp4"))
            videos_left = len([v for v in all_videos if str(v) not in posted_videos])
        
        console.print(f"  {email} -> {folder} ({videos_left} videos còn lại)")
    
    # Available folders
    available = get_available_folders()
    assigned = set(mapping.values())
    unassigned = [f for f in available if f not in assigned]
    
    console.print(f"\n[bold]Folders chưa gán:[/bold] {len(unassigned)}")
    for f in unassigned[:5]:
        console.print(f"  - {f}")
    if len(unassigned) > 5:
        console.print(f"  ... và {len(unassigned) - 5} folders khác")
    
    # Hashtags
    hashtags = load_hashtags()
    console.print(f"\n[bold]Hashtags:[/bold] {len(hashtags)}")


def main():
    """Main function"""
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "run":
            run_once()
        elif cmd == "schedule":
            run_scheduler()
        elif cmd == "status":
            show_status()
        else:
            console.print(f"[red]Lệnh không hợp lệ: {cmd}[/red]")
    else:
        console.print(Panel(
            "[bold magenta]TikTok Auto Poster[/bold magenta]\n"
            "[dim]Đăng video TikTok tự động[/dim]",
            border_style="magenta"
        ))
        
        console.print("\n[bold]Cách dùng:[/bold]")
        console.print("  python auto_post.py run      - Đăng ngay 1 lần")
        console.print("  python auto_post.py schedule - Chạy scheduler tự động")
        console.print("  python auto_post.py status   - Xem trạng thái")
        
        console.print("\n[bold]Files cần có:[/bold]")
        console.print(f"  accounts.txt  - Danh sách account (mail:pass)")
        console.print(f"  hashtags.txt  - Danh sách hashtags")
        console.print(f"  TikTok_Downloads/ - Videos từ ytdl.py")


if __name__ == "__main__":
    main()
