#!/usr/bin/env python3
"""
TikTok Auto Poster - Đăng video TikTok tự động theo lịch (Selenium version)

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
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    print("Cần cài đặt: pip install selenium webdriver-manager rich")
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
COOKIES_DIR = Path(__file__).parent / "cookies"

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
            videos = list(item.glob("*.mp4"))
            if videos:
                folders.append(item.name)
    
    return folders


def assign_folder_to_account(account_email: str) -> Optional[str]:
    """Gán folder cho account (nếu chưa có)"""
    mapping = get_account_folder_map()
    
    if account_email in mapping:
        return mapping[account_email]
    
    assigned_folders = set(mapping.values())
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
    
    all_videos = list(folder_path.glob("*.mp4"))
    
    for video in sorted(all_videos):
        if str(video) not in posted_videos:
            return video
    
    return None


def filename_to_caption(filename: str) -> str:
    """Chuyển tên file thành caption"""
    name = Path(filename).stem
    name = re.sub(r'_[a-zA-Z0-9]{6,}$', '', name)
    name = name.replace("_", " ")
    return name.strip()


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
    
    start_hour, end_hour = SCHEDULE[slot]
    random_hour = random.randint(start_hour, end_hour - 1)
    random_minute = random.randint(0, 59)
    
    next_time = datetime.combine(base_date, datetime.min.time())
    next_time = next_time.replace(hour=random_hour, minute=random_minute)
    
    return slot, next_time


# ========== SELENIUM AUTOMATION ==========
def create_driver(headless: bool = False) -> webdriver.Chrome:
    """Tạo Chrome driver"""
    options = Options()
    
    if headless:
        options.add_argument("--headless=new")
    
    # Tránh detect bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    
    # User agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Thêm script chống detect
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def save_cookies(driver: webdriver.Chrome, email: str) -> None:
    """Lưu cookies sau khi login"""
    COOKIES_DIR.mkdir(exist_ok=True)
    cookies = driver.get_cookies()
    cookie_file = COOKIES_DIR / f"{email.replace('@', '_at_')}.json"
    save_json(cookie_file, cookies)
    console.print(f"[green]Đã lưu cookies: {cookie_file.name}[/green]")


def load_cookies(driver: webdriver.Chrome, email: str) -> bool:
    """Load cookies nếu có"""
    cookie_file = COOKIES_DIR / f"{email.replace('@', '_at_')}.json"
    if not cookie_file.exists():
        return False
    
    try:
        driver.get("https://www.tiktok.com")
        time.sleep(2)
        
        cookies = load_json(cookie_file)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        
        driver.refresh()
        time.sleep(3)
        
        # Kiểm tra đã login chưa
        if "login" not in driver.current_url.lower():
            console.print(f"[green]Đã load cookies thành công[/green]")
            return True
        
        return False
        
    except Exception as e:
        console.print(f"[yellow]Lỗi load cookies: {e}[/yellow]")
        return False


def login_tiktok(driver: webdriver.Chrome, email: str, password: str) -> bool:
    """Đăng nhập TikTok"""
    try:
        console.print(f"[cyan]Đang đăng nhập {email}...[/cyan]")
        
        # Thử load cookies trước
        if load_cookies(driver, email):
            return True
        
        # Login thủ công
        driver.get("https://www.tiktok.com/login/phone-or-email/email")
        time.sleep(3)
        
        # Chờ và nhập email
        wait = WebDriverWait(driver, 20)
        
        email_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[name="username"]')
        ))
        email_input.clear()
        for char in email:
            email_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(1)
        
        # Nhập password
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        password_input.clear()
        for char in password:
            password_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(1)
        
        # Click login
        login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_btn.click()
        
        # Chờ kết quả
        time.sleep(5)
        
        # Kiểm tra CAPTCHA
        if "captcha" in driver.current_url.lower() or "verify" in driver.page_source.lower():
            console.print("[yellow]Cần xác thực CAPTCHA - Vui lòng giải thủ công...[/yellow]")
            console.print("[dim]Nhấn Enter sau khi giải xong...[/dim]")
            input()
        
        # Chờ redirect
        time.sleep(5)
        
        # Kiểm tra thành công
        if "foryou" in driver.current_url or "/@" in driver.current_url:
            console.print(f"[green]Đăng nhập thành công: {email}[/green]")
            save_cookies(driver, email)
            return True
        
        console.print(f"[red]Đăng nhập thất bại - URL: {driver.current_url}[/red]")
        return False
        
    except Exception as e:
        console.print(f"[red]Lỗi đăng nhập: {e}[/red]")
        return False


def upload_video(driver: webdriver.Chrome, video_path: Path, caption: str) -> bool:
    """Upload video lên TikTok"""
    try:
        console.print(f"[cyan]Đang upload: {video_path.name}[/cyan]")
        console.print(f"[dim]Caption: {caption}[/dim]")
        
        # Vào trang upload - thử nhiều URL
        upload_urls = [
            "https://www.tiktok.com/creator-center/upload",
            "https://www.tiktok.com/upload",
            "https://www.tiktok.com/tiktokstudio/upload"
        ]
        
        for url in upload_urls:
            driver.get(url)
            time.sleep(5)
            
            # Kiểm tra có phải trang upload không
            if "upload" in driver.current_url.lower():
                console.print(f"[dim]Đang dùng: {url}[/dim]")
                break
        
        # Đóng popup "Got it" nếu có
        popup_buttons = [
            '//button[contains(text(), "Got it")]',
            '//button[contains(text(), "OK")]',
            '//button[contains(text(), "Dismiss")]',
            '//button[contains(text(), "Close")]',
            '//button[contains(text(), "Skip")]',
            '//div[contains(text(), "Got it")]',
            '//span[contains(text(), "Got it")]',
            '[class*="close"]',
            '[class*="dismiss"]',
            '[aria-label="Close"]',
            '[aria-label="Dismiss"]'
        ]
        
        for selector in popup_buttons:
            try:
                if selector.startswith('//'):
                    btn = driver.find_element(By.XPATH, selector)
                else:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                
                if btn.is_displayed():
                    btn.click()
                    console.print(f"[dim]Đã đóng popup[/dim]")
                    time.sleep(1)
            except Exception:
                continue
        
        wait = WebDriverWait(driver, 30)
        
        # Upload file - thử nhiều selectors
        file_selectors = [
            'input[type="file"]',
            'input[accept*="video"]',
            'input[name="upload-btn"]',
            '[data-testid="upload-input"]'
        ]
        
        file_input = None
        for selector in file_selectors:
            try:
                file_input = driver.find_element(By.CSS_SELECTOR, selector)
                if file_input:
                    console.print(f"[dim]Tìm thấy input với: {selector}[/dim]")
                    break
            except Exception:
                continue
        
        if not file_input:
            # Thử tìm trong iframe
            try:
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                for iframe in iframes:
                    try:
                        driver.switch_to.frame(iframe)
                        file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                        if file_input:
                            console.print("[dim]Tìm thấy input trong iframe[/dim]")
                            break
                    except Exception:
                        driver.switch_to.default_content()
                        continue
            except Exception:
                pass
        
        if not file_input:
            console.print("[red]Không tìm thấy input upload[/red]")
            # Debug: in ra HTML
            console.print(f"[dim]Current URL: {driver.current_url}[/dim]")
            return False
        
        file_input.send_keys(str(video_path.absolute()))
        console.print("[dim]Đang upload video...[/dim]")
        
        # Chờ upload xong
        time.sleep(20)
        
        # Chuyển về main frame
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        
        # Đóng TẤT CẢ popup có thể xuất hiện sau upload
        console.print("[dim]Kiểm tra và đóng popups...[/dim]")
        for _ in range(3):  # Thử 3 lần vì có thể có nhiều popup
            popup_closed = False
            popup_selectors = [
                '//button[contains(text(), "Got it")]',
                '//button[contains(text(), "OK")]', 
                '//button[contains(text(), "Skip")]',
                '//button[contains(text(), "Next")]',
                '//button[contains(text(), "Continue")]',
                '//span[contains(text(), "Got it")]',
                '//div[contains(text(), "Got it")]',
                '//button[@aria-label="Close"]',
                '//button[contains(@class, "close")]',
                '//div[contains(@class, "modal")]//button',
            ]
            
            for selector in popup_selectors:
                try:
                    btns = driver.find_elements(By.XPATH, selector)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            console.print(f"[dim]Đóng popup: {selector.split('\"')[1] if '\"' in selector else 'button'}[/dim]")
                            popup_closed = True
                            time.sleep(1)
                            break
                except Exception:
                    continue
            
            if not popup_closed:
                break
            time.sleep(1)
        
        time.sleep(2)
        
        # Đóng popup "Turn on automatic content checks?" -> Click Cancel
        try:
            # Tìm popup và click Cancel
            cancel_selectors = [
                '//div[contains(text(), "Turn on automatic content checks")]//ancestor::div//button[contains(text(), "Cancel")]',
                '//button[text()="Cancel"]',
                '//span[text()="Cancel"]//ancestor::button',
                '//div[contains(@class, "modal")]//button[contains(text(), "Cancel")]'
            ]
            
            for selector in cancel_selectors:
                try:
                    btn = driver.find_element(By.XPATH, selector)
                    if btn.is_displayed():
                        btn.click()
                        console.print("[dim]Đã click Cancel (automatic content checks)[/dim]")
                        time.sleep(1)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        # TẮT các toggle checks (Music copyright check, Content check lite)
        console.print("[dim]Kiểm tra và tắt các content checks...[/dim]")
        
        # Scroll xuống để thấy phần Checks
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5)")
            time.sleep(1)
        except Exception:
            pass
        
        # Tìm tất cả toggle switches và tắt
        try:
            # Tìm tất cả toggle có role="switch" 
            toggles = driver.find_elements(By.CSS_SELECTOR, '[role="switch"]')
            console.print(f"[dim]Tìm thấy {len(toggles)} toggles[/dim]")
            
            for toggle in toggles:
                try:
                    is_on = toggle.get_attribute('aria-checked') == 'true'
                    if is_on:
                        # Scroll vào view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", toggle)
                        time.sleep(0.5)
                        
                        # Dùng JavaScript click (reliable hơn)
                        driver.execute_script("arguments[0].click();", toggle)
                        console.print("[dim]Đã tắt 1 toggle (JS click)[/dim]")
                        time.sleep(1)
                        
                        # Verify đã tắt
                        if toggle.get_attribute('aria-checked') == 'false':
                            console.print("[dim]Toggle đã tắt thành công[/dim]")
                except Exception as e:
                    console.print(f"[dim]Lỗi toggle: {e}[/dim]")
                    continue
        except Exception as e:
            console.print(f"[yellow]Không tìm thấy toggles: {e}[/yellow]")
        
        # Thử cách khác: tìm theo class chứa "switch" hoặc "toggle"
        try:
            other_toggles = driver.find_elements(By.CSS_SELECTOR, '[class*="switch"], [class*="toggle"]')
            for toggle in other_toggles:
                try:
                    # Kiểm tra nếu là switch đang ON
                    classes = toggle.get_attribute('class') or ''
                    if 'checked' in classes or 'active' in classes or 'on' in classes:
                        driver.execute_script("arguments[0].click();", toggle)
                        console.print("[dim]Đã click toggle (class)[/dim]")
                        time.sleep(0.5)
                except Exception:
                    continue
        except Exception:
            pass
        
        time.sleep(1)
        
        # Đóng popup "Content may be restricted" nếu có
        try:
            # Tìm nút X đóng popup
            close_btns = driver.find_elements(By.XPATH, 
                '//div[contains(text(), "Content may be restricted")]//ancestor::div[contains(@class, "modal") or contains(@class, "dialog")]//button | ' +
                '//button[@aria-label="Close"] | ' +
                '//button[contains(@class, "close")] | ' +
                '//*[contains(text(), "Content may be restricted")]//ancestor::div//button[.//svg]'
            )
            
            for btn in close_btns:
                if btn.is_displayed():
                    btn.click()
                    console.print("[dim]Đã đóng popup cảnh báo[/dim]")
                    time.sleep(1)
                    break
        except Exception:
            pass
        
        # Click vào nơi khác để đóng popup nếu còn
        try:
            driver.find_element(By.TAG_NAME, 'body').click()
            time.sleep(0.5)
        except Exception:
            pass
        
        # Đóng popup "Got it" lần nữa nếu có (trước khi nhập caption)
        for selector in ['//button[contains(text(), "Got it")]', '//button[contains(text(), "OK")]', '//span[contains(text(), "Got it")]']:
            try:
                btn = driver.find_element(By.XPATH, selector)
                if btn.is_displayed():
                    btn.click()
                    console.print(f"[dim]Đã đóng popup (caption)[/dim]")
                    time.sleep(1)
            except Exception:
                continue
        
        # Nhập caption - thử nhiều selectors
        caption_selectors = [
            '[contenteditable="true"]',
            '[data-contents="true"]',
            '.public-DraftEditor-content',
            '[class*="caption"]',
            '[class*="editor"]',
            'textarea',
            '[role="textbox"]'
        ]
        
        caption_entered = False
        caption_elem = None
        
        for selector in caption_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        elem.click()
                        time.sleep(0.5)
                        elem.send_keys(Keys.CONTROL + "a")
                        elem.send_keys(Keys.DELETE)
                        time.sleep(0.3)
                        
                        # Tách caption và hashtags
                        caption_parts = caption.split("#")
                        main_caption = caption_parts[0].strip()
                        hashtags = ["#" + tag.strip() for tag in caption_parts[1:] if tag.strip()]
                        
                        # Nhập caption chính
                        for char in main_caption:
                            elem.send_keys(char)
                            time.sleep(random.uniform(0.02, 0.05))
                        
                        # Thêm space trước hashtags
                        if hashtags:
                            elem.send_keys(" ")
                            time.sleep(0.3)
                        
                        # Nhập từng hashtag và nhấn Space để TikTok nhận diện
                        for tag in hashtags:
                            # Gõ hashtag
                            for char in tag:
                                elem.send_keys(char)
                                time.sleep(random.uniform(0.02, 0.05))
                            
                            time.sleep(0.5)  # Chờ dropdown suggestion
                            
                            # Nhấn Space để confirm hashtag
                            elem.send_keys(" ")
                            time.sleep(0.3)
                            
                            console.print(f"[dim]Đã nhập hashtag: {tag}[/dim]")
                        
                        console.print(f"[dim]Đã nhập caption với: {selector}[/dim]")
                        caption_entered = True
                        caption_elem = elem
                        break
                if caption_entered:
                    break
            except Exception:
                continue
        
        if not caption_entered:
            console.print("[yellow]Không nhập được caption[/yellow]")
        
        time.sleep(3)
        
        # Đóng popup lần nữa trước khi Post (nếu có)
        for selector in ['//button[contains(text(), "Got it")]', '//button[contains(text(), "OK")]']:
            try:
                btn = driver.find_element(By.XPATH, selector)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
            except Exception:
                continue
        
        # Click Post - TÌM CHÍNH XÁC, TRÁNH NHẦM EXIT
        # Blacklist các từ khóa của nút Exit/Cancel
        blacklist_words = ['exit', 'cancel', 'close', 'discard', 'delete', 'remove', 'hủy', 'thoát', 'xóa']
        
        post_clicked = False
        
        # Tìm tất cả buttons và lọc
        try:
            buttons = driver.find_elements(By.TAG_NAME, 'button')
            console.print(f"[dim]Tìm thấy {len(buttons)} buttons[/dim]")
            
            for btn in buttons:
                try:
                    btn_text = btn.text.lower().strip()
                    btn_class = btn.get_attribute('class') or ''
                    
                    # Skip nếu chứa blacklist words
                    if any(word in btn_text for word in blacklist_words):
                        continue
                    if any(word in btn_class.lower() for word in blacklist_words):
                        continue
                    
                    # Tìm nút Post/Đăng/Publish
                    if btn_text in ['post', 'đăng', 'publish', 'submit']:
                        if btn.is_displayed() and btn.is_enabled():
                            console.print(f"[dim]Tìm thấy nút: '{btn.text}'[/dim]")
                            btn.click()
                            post_clicked = True
                            break
                    
                    # Hoặc class chứa post/submit
                    if 'post' in btn_class.lower() or 'submit' in btn_class.lower() or 'publish' in btn_class.lower():
                        if btn.is_displayed() and btn.is_enabled():
                            # Double check không phải exit
                            if 'exit' not in btn_text and 'cancel' not in btn_text:
                                console.print(f"[dim]Tìm thấy nút (class): '{btn.text}' class={btn_class[:30]}[/dim]")
                                btn.click()
                                post_clicked = True
                                break
                                
                except Exception:
                    continue
        except Exception as e:
            console.print(f"[yellow]Lỗi tìm buttons: {e}[/yellow]")
        
        # Thử XPath nếu chưa click được
        if not post_clicked:
            post_xpaths = [
                '//button[text()="Post"]',
                '//button[text()="Đăng"]',
                '//button[text()="Publish"]',
                '//button[.//span[text()="Post"]]',
                '//button[.//div[text()="Post"]]'
            ]
            
            for xpath in post_xpaths:
                try:
                    btn = driver.find_element(By.XPATH, xpath)
                    btn_text = btn.text.lower()
                    
                    # Skip nếu là exit
                    if any(word in btn_text for word in blacklist_words):
                        continue
                    
                    if btn.is_displayed() and btn.is_enabled():
                        console.print(f"[dim]Clicked với xpath[/dim]")
                        btn.click()
                        post_clicked = True
                        break
                except Exception:
                    continue
        
        if post_clicked:
            console.print("[dim]Đang đăng... chờ xác nhận...[/dim]")
            
            # Chờ và verify đã đăng xong
            upload_success = False
            for i in range(30):  # Chờ tối đa 30s
                time.sleep(1)
                
                try:
                    # Check 1: URL đổi sang profile hoặc manage
                    current_url = driver.current_url.lower()
                    if '/manage' in current_url or '/@' in current_url or 'profile' in current_url:
                        upload_success = True
                        console.print("[dim]Đã redirect sang profile/manage[/dim]")
                        break
                    
                    # Check 2: Có thông báo success
                    success_texts = ['posted', 'published', 'uploaded', 'success', 'thành công']
                    page_text = driver.page_source.lower()
                    if any(txt in page_text for txt in success_texts):
                        upload_success = True
                        console.print("[dim]Phát hiện thông báo thành công[/dim]")
                        break
                    
                    # Check 3: Nút Post biến mất hoặc disabled
                    try:
                        post_btn = driver.find_element(By.XPATH, '//button[text()="Post"]')
                        if not post_btn.is_displayed():
                            upload_success = True
                            console.print("[dim]Nút Post đã biến mất[/dim]")
                            break
                    except Exception:
                        # Không tìm thấy nút Post = đã đăng xong
                        upload_success = True
                        break
                        
                except Exception:
                    continue
                
                if i % 5 == 0:
                    console.print(f"[dim]Đang chờ... {i}s[/dim]")
            
            if upload_success:
                console.print(f"[green]Đăng thành công: {video_path.name}[/green]")
                return True
            else:
                console.print("[yellow]Không xác nhận được đã đăng, kiểm tra thủ công...[/yellow]")
                input("Nhấn Enter sau khi xác nhận đã đăng xong...")
                return True
        else:
            console.print("[red]Không tìm thấy nút Post[/red]")
            # Debug: liệt kê các buttons
            try:
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                console.print(f"[dim]Các buttons trên trang ({len(buttons)}):[/dim]")
                for i, btn in enumerate(buttons[:15]):
                    txt = btn.text[:40] if btn.text else "(no text)"
                    cls = (btn.get_attribute('class') or '')[:30]
                    console.print(f"  [{i}] text='{txt}' class='{cls}' visible={btn.is_displayed()}")
            except Exception:
                pass
            
            console.print("[yellow]Vui lòng click nút Post thủ công, rồi nhấn Enter...[/yellow]")
            input()
            return True
        
    except Exception as e:
        console.print(f"[red]Lỗi upload: {e}[/red]")
        return False


def post_video_for_account(account: dict, headless: bool = False) -> bool:
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
    driver = None
    try:
        driver = create_driver(headless=headless)
        
        # Đăng nhập
        if not login_tiktok(driver, email, password):
            return False
        
        # Upload video
        if upload_video(driver, video, full_caption):
            mark_video_posted(email, str(video))
            return True
        
        return False
        
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/red]")
        return False
        
    finally:
        if driver:
            driver.quit()


# ========== SCHEDULER ==========
def run_scheduler(headless: bool = False):
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
            
            for account in accounts:
                try:
                    post_video_for_account(account, headless=headless)
                    delay = random.randint(60, 180)
                    console.print(f"[dim]Chờ {delay}s trước account tiếp theo...[/dim]")
                    time.sleep(delay)
                except Exception as e:
                    console.print(f"[red]Lỗi: {e}[/red]")
            
            posted_today[current_slot] = True
            console.print(f"[green]Hoàn thành slot {current_slot}[/green]")
        
        # Reset vào 0h
        if now.hour == 0 and now.minute < 5:
            posted_today = {slot: False for slot in SCHEDULE.keys()}
        
        # Hiển thị next slot
        next_slot, next_time = get_next_slot_time()
        wait_seconds = (next_time - now).total_seconds()
        
        if wait_seconds > 0:
            console.print(f"[dim]Next: {next_slot} @ {next_time.strftime('%H:%M')} (chờ {int(wait_seconds/60)} phút)[/dim]")
        
        time.sleep(300)


def run_once(headless: bool = False):
    """Chạy đăng 1 lần"""
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
            post_video_for_account(account, headless=headless)
        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/red]")
        
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
    
    accounts = load_accounts()
    console.print(f"\n[bold]Accounts ({len(accounts)}):[/bold]")
    for acc in accounts:
        console.print(f"  - {acc['email']}")
    
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
    
    available = get_available_folders()
    assigned = set(mapping.values())
    unassigned = [f for f in available if f not in assigned]
    
    console.print(f"\n[bold]Folders chưa gán:[/bold] {len(unassigned)}")
    for f in unassigned[:5]:
        console.print(f"  - {f}")
    if len(unassigned) > 5:
        console.print(f"  ... và {len(unassigned) - 5} folders khác")
    
    hashtags = load_hashtags()
    console.print(f"\n[bold]Hashtags:[/bold] {len(hashtags)}")
    
    # Cookies
    if COOKIES_DIR.exists():
        cookies = list(COOKIES_DIR.glob("*.json"))
        console.print(f"\n[bold]Saved cookies:[/bold] {len(cookies)}")


def main():
    """Main function"""
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        headless = "--headless" in sys.argv
        
        if cmd == "run":
            run_once(headless=headless)
        elif cmd == "schedule":
            run_scheduler(headless=headless)
        elif cmd == "status":
            show_status()
        else:
            console.print(f"[red]Lệnh không hợp lệ: {cmd}[/red]")
    else:
        console.print(Panel(
            "[bold magenta]TikTok Auto Poster[/bold magenta]\n"
            "[dim]Selenium version - Dùng Chrome có sẵn[/dim]",
            border_style="magenta"
        ))
        
        console.print("\n[bold]Cách dùng:[/bold]")
        console.print("  python auto_post.py run           - Đăng ngay 1 lần")
        console.print("  python auto_post.py run --headless- Đăng ẩn (không hiện browser)")
        console.print("  python auto_post.py schedule      - Chạy scheduler tự động")
        console.print("  python auto_post.py status        - Xem trạng thái")
        
        console.print("\n[bold]Files cần có:[/bold]")
        console.print(f"  accounts.txt     - Danh sách account (mail:pass)")
        console.print(f"  hashtags.txt     - Danh sách hashtags")
        console.print(f"  TikTok_Downloads/- Videos từ ytdl.py")
        
        console.print("\n[bold]Cài đặt:[/bold]")
        console.print("  pip install selenium webdriver-manager rich")


if __name__ == "__main__":
    main()
