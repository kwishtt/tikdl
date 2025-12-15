#!/usr/bin/env python3
"""
TikTok Account Generator - Tạo tài khoản TikTok với temp mail

Flow:
1. Tạo email tạm từ mail.tm
2. Mở browser đăng ký TikTok
3. Nhập thông tin, nhận OTP từ email
4. Hoàn thành đăng ký
5. Lưu account và cookies

Chạy: python reg.py
"""

import json
import random
import string
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

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
    from rich.prompt import Prompt
except ImportError:
    print("Cần cài đặt: pip install selenium webdriver-manager rich requests")
    sys.exit(1)

# ========== CONFIG ==========
console = Console()

ACCOUNTS_FILE = Path(__file__).parent / "accounts.txt"
COOKIES_DIR = Path(__file__).parent / "cookies"
GENERATED_FILE = Path(__file__).parent / "generated_accounts.json"

# Temp mail API (mail.tm)
MAIL_API = "https://api.mail.tm"


# ========== TEMP MAIL FUNCTIONS ==========
class TempMail:
    """Quản lý temp mail từ mail.tm"""
    
    def __init__(self):
        self.session = requests.Session()
        self.email = None
        self.password = None
        self.token = None
        self.account_id = None
    
    def get_domains(self) -> list:
        """Lấy danh sách domains có sẵn"""
        try:
            resp = self.session.get(f"{MAIL_API}/domains")
            if resp.status_code == 200:
                data = resp.json()
                return [d["domain"] for d in data.get("hydra:member", [])]
        except Exception as e:
            console.print(f"[red]Lỗi lấy domains: {e}[/red]")
        return []
    
    def create_account(self) -> bool:
        """Tạo tài khoản email mới"""
        domains = self.get_domains()
        if not domains:
            console.print("[red]Không lấy được domains[/red]")
            return False
        
        # Random username và password
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(domains)
        self.email = f"{username}@{domain}"
        self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # Tạo account
        try:
            resp = self.session.post(
                f"{MAIL_API}/accounts",
                json={
                    "address": self.email,
                    "password": self.password
                }
            )
            
            if resp.status_code == 201:
                data = resp.json()
                self.account_id = data.get("id")
                console.print(f"[green]Đã tạo email: {self.email}[/green]")
                return self.login()
            else:
                console.print(f"[red]Lỗi tạo email: {resp.text}[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/red]")
            return False
    
    def login(self) -> bool:
        """Đăng nhập để lấy token"""
        try:
            resp = self.session.post(
                f"{MAIL_API}/token",
                json={
                    "address": self.email,
                    "password": self.password
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                self.session.headers["Authorization"] = f"Bearer {self.token}"
                return True
            else:
                console.print(f"[red]Lỗi login mail: {resp.text}[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/red]")
            return False
    
    def get_messages(self) -> list:
        """Lấy danh sách emails"""
        try:
            resp = self.session.get(f"{MAIL_API}/messages")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("hydra:member", [])
        except Exception as e:
            console.print(f"[red]Lỗi lấy messages: {e}[/red]")
        return []
    
    def get_message(self, message_id: str) -> dict:
        """Lấy nội dung 1 email"""
        try:
            resp = self.session.get(f"{MAIL_API}/messages/{message_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            console.print(f"[red]Lỗi lấy message: {e}[/red]")
        return {}
    
    def wait_for_otp(self, timeout: int = 120) -> str:
        """Chờ và lấy OTP từ email TikTok"""
        console.print(f"[dim]Đang chờ email OTP (tối đa {timeout}s)...[/dim]")
        
        start_time = time.time()
        checked_ids = set()
        
        while time.time() - start_time < timeout:
            messages = self.get_messages()
            
            for msg in messages:
                msg_id = msg.get("id")
                if msg_id in checked_ids:
                    continue
                
                checked_ids.add(msg_id)
                
                # Kiểm tra email từ TikTok
                sender = msg.get("from", {}).get("address", "").lower()
                subject = msg.get("subject", "").lower()
                
                if "tiktok" in sender or "tiktok" in subject or "verify" in subject:
                    # Lấy nội dung email
                    full_msg = self.get_message(msg_id)
                    text = full_msg.get("text", "") or full_msg.get("html", "")
                    
                    # Tìm OTP (thường là 6 số)
                    import re
                    otp_match = re.search(r'\b(\d{6})\b', text)
                    if otp_match:
                        otp = otp_match.group(1)
                        console.print(f"[green]Nhận được OTP: {otp}[/green]")
                        return otp
            
            time.sleep(3)
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                console.print(f"[dim]Đang chờ... {elapsed}s[/dim]")
        
        console.print("[red]Hết thời gian chờ OTP[/red]")
        return ""


# Random User Agents
USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Windows Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Mac Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Thư mục lưu temp profiles
PROFILES_DIR = Path(__file__).parent / "chrome_profiles"


def create_fresh_profile() -> Path:
    """Tạo Chrome profile mới sạch"""
    PROFILES_DIR.mkdir(exist_ok=True)
    
    # Tạo tên profile unique
    profile_name = f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
    profile_path = PROFILES_DIR / profile_name
    profile_path.mkdir(exist_ok=True)
    
    console.print(f"[dim]New profile: {profile_name}[/dim]")
    return profile_path


def cleanup_old_profiles():
    """Xóa các profiles cũ (giữ 5 profiles gần nhất)"""
    if not PROFILES_DIR.exists():
        return
    
    profiles = sorted(PROFILES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Xóa profiles cũ, giữ 5 cái mới nhất
    for profile in profiles[5:]:
        try:
            import shutil
            shutil.rmtree(profile)
            console.print(f"[dim]Đã xóa profile cũ: {profile.name}[/dim]")
        except Exception:
            pass


def create_driver() -> webdriver.Chrome:
    """Tạo Chrome driver với fresh profile và random fingerprint"""
    options = Options()
    
    # Tạo profile mới sạch
    profile_path = create_fresh_profile()
    options.add_argument(f"--user-data-dir={profile_path}")
    
    # Random user agent
    user_agent = random.choice(USER_AGENTS)
    console.print(f"[dim]User-Agent: {user_agent[:50]}...[/dim]")
    
    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Random window size
    widths = [1366, 1440, 1536, 1600, 1920]
    heights = [768, 900, 864, 900, 1080]
    idx = random.randint(0, len(widths) - 1)
    window_size = f"--window-size={widths[idx]},{heights[idx]}"
    options.add_argument(window_size)
    
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-agent={user_agent}")
    
    # Thêm các flags để tránh fingerprinting
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")
    
    # Random language
    languages = ["en-US,en", "en-GB,en", "vi-VN,vi,en"]
    options.add_argument(f"--lang={random.choice(languages)}")
    
    # Disable webrtc leak
    options.add_argument("--disable-webrtc")
    
    # Disable cache
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-cache")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Inject scripts để fake fingerprint
    try:
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": user_agent,
            "platform": "Win32" if "Windows" in user_agent else "MacIntel" if "Mac" in user_agent else "Linux x86_64"
        })
    except Exception:
        pass
    
    # Override navigator properties
    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        
        // Fake canvas fingerprint
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (type === 'image/png' && this.width === 16 && this.height === 16) {
                return 'data:image/png;base64,fake';
            }
            return originalToDataURL.apply(this, arguments);
        };
        
        // Fake WebGL
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.apply(this, arguments);
        };
    """)
    
    return driver


def save_cookies(driver: webdriver.Chrome, email: str) -> None:
    """Lưu cookies"""
    COOKIES_DIR.mkdir(exist_ok=True)
    cookies = driver.get_cookies()
    cookie_file = COOKIES_DIR / f"{email.replace('@', '_at_')}.json"
    
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    
    console.print(f"[green]Đã lưu cookies: {cookie_file.name}[/green]")


def save_account(email: str, password: str) -> None:
    """Lưu account vào file"""
    # Thêm vào accounts.txt
    with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{email}:{password}\n")
    
    # Lưu vào generated_accounts.json
    generated = {}
    if GENERATED_FILE.exists():
        with open(GENERATED_FILE, "r", encoding="utf-8") as f:
            generated = json.load(f)
    
    generated[email] = {
        "password": password,
        "created_at": datetime.now().isoformat()
    }
    
    with open(GENERATED_FILE, "w", encoding="utf-8") as f:
        json.dump(generated, f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]Đã lưu account: {email}[/green]")


def random_password() -> str:
    """Tạo password theo format DinhKhue@<random_number>"""
    num = random.randint(1000, 9999)
    return f"DinhKhue@{num}"


def random_username() -> str:
    """Tạo username ngẫu nhiên"""
    adjectives = ["cool", "happy", "smart", "fast", "nice", "cute", "sweet", "wild"]
    nouns = ["tiger", "dragon", "phoenix", "star", "moon", "sun", "wolf", "fox"]
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    num = random.randint(100, 9999)
    return f"{adj}{noun}{num}"


def random_birthday() -> tuple:
    """Tạo ngày sinh ngẫu nhiên (18-30 tuổi)"""
    year = random.randint(1994, 2006)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return year, month, day


def register_tiktok(temp_mail: TempMail) -> bool:
    """Đăng ký tài khoản TikTok"""
    driver = None
    
    try:
        console.print("\n[bold cyan]Bắt đầu đăng ký TikTok...[/bold cyan]")
        
        driver = create_driver()
        wait = WebDriverWait(driver, 20)
        
        # Vào trang đăng ký
        driver.get("https://www.tiktok.com/signup/phone-or-email/email")
        time.sleep(5)
        
        # Chọn ngày sinh - Click dropdown rồi chọn từ list
        console.print("[dim]Chọn ngày sinh...[/dim]")
        year, month, day = random_birthday()
        
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        
        birthday_selected = False
        
        try:
            # Tìm 3 dropdown boxes (Month, Day, Year)
            # Thường có placeholder hoặc text "Month", "Day", "Year"
            
            # === MONTH ===
            console.print(f"[dim]Chọn tháng: {month_names[month-1]}[/dim]")
            try:
                # Click vào dropdown Month
                month_dropdown = driver.find_element(By.XPATH, 
                    '//*[contains(text(), "Month")] | //*[@placeholder="Month"]'
                )
                month_dropdown.click()
                time.sleep(0.5)
                
                # Chọn tháng từ list
                month_option = driver.find_element(By.XPATH, 
                    f'//div[text()="{month_names[month-1]}"] | //span[text()="{month_names[month-1]}"] | //li[text()="{month_names[month-1]}"]'
                )
                month_option.click()
                console.print(f"[green]Đã chọn tháng: {month_names[month-1]}[/green]")
                time.sleep(0.5)
            except Exception as e:
                console.print(f"[yellow]Lỗi chọn tháng: {e}[/yellow]")
            
            # === DAY ===
            console.print(f"[dim]Chọn ngày: {day}[/dim]")
            try:
                # Click vào dropdown Day
                day_dropdown = driver.find_element(By.XPATH, 
                    '//*[contains(text(), "Day")] | //*[@placeholder="Day"]'
                )
                day_dropdown.click()
                time.sleep(0.5)
                
                # Chọn ngày từ list
                day_option = driver.find_element(By.XPATH, 
                    f'//div[text()="{day}"] | //span[text()="{day}"] | //li[text()="{day}"]'
                )
                day_option.click()
                console.print(f"[green]Đã chọn ngày: {day}[/green]")
                time.sleep(0.5)
            except Exception as e:
                console.print(f"[yellow]Lỗi chọn ngày: {e}[/yellow]")
            
            # === YEAR ===
            console.print(f"[dim]Chọn năm: {year}[/dim]")
            try:
                # Click vào dropdown Year
                year_dropdown = driver.find_element(By.XPATH, 
                    '//*[contains(text(), "Year")] | //*[@placeholder="Year"]'
                )
                year_dropdown.click()
                time.sleep(0.5)
                
                # Chọn năm từ list
                year_option = driver.find_element(By.XPATH, 
                    f'//div[text()="{year}"] | //span[text()="{year}"] | //li[text()="{year}"]'
                )
                year_option.click()
                console.print(f"[green]Đã chọn năm: {year}[/green]")
                time.sleep(0.5)
            except Exception as e:
                console.print(f"[yellow]Lỗi chọn năm: {e}[/yellow]")
            
            birthday_selected = True
            
        except Exception as e:
            console.print(f"[yellow]Lỗi chọn ngày sinh: {e}[/yellow]")
        
        # Nếu không tự động được, hỏi thủ công
        if not birthday_selected:
            console.print("[yellow]Không tự động chọn được ngày sinh[/yellow]")
            console.print("[yellow]Vui lòng chọn ngày sinh thủ công trong browser...[/yellow]")
            input("Nhấn Enter sau khi chọn xong ngày sinh...")
        
        time.sleep(1)
        
        # Nhập email
        console.print(f"[dim]Nhập email: {temp_mail.email}[/dim]")
        try:
            email_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[name="email"], input[type="email"]')
            ))
            email_input.clear()
            for char in temp_mail.email:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.03, 0.08))
        except Exception as e:
            console.print(f"[yellow]Lỗi nhập email: {e}[/yellow]")
        
        time.sleep(1)
        
        # Nhập password
        tiktok_password = random_password()
        console.print(f"[dim]Nhập password: {tiktok_password}[/dim]")
        try:
            password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
            password_input.clear()
            for char in tiktok_password:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.03, 0.08))
        except Exception as e:
            console.print(f"[yellow]Lỗi nhập password: {e}[/yellow]")
        
        time.sleep(2)
        
        # Thử click Send code
        console.print("[dim]Đang tìm nút Send code...[/dim]")
        send_clicked = False
        
        # Tìm tất cả elements có thể là nút Send code
        try:
            # Cách 1: Tìm bằng text
            all_elements = driver.find_elements(By.XPATH, '//*[contains(text(), "Send code") or contains(text(), "send code")]')
            console.print(f"[dim]Tìm thấy {len(all_elements)} elements chứa 'Send code'[/dim]")
            
            for elem in all_elements:
                try:
                    if elem.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                        time.sleep(0.3)
                        driver.execute_script("arguments[0].click();", elem)
                        console.print(f"[green]Đã JS click: {elem.tag_name}[/green]")
                        send_clicked = True
                        time.sleep(2)
                        break
                except Exception:
                    continue
            
            # Cách 2: Tìm theo CSS class
            if not send_clicked:
                css_selectors = [
                    '[class*="sendCode"]',
                    '[class*="send-code"]',
                    '[data-e2e*="send"]',
                    'a[href*="send"]',
                ]
                for css in css_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, css)
                        if elem.is_displayed():
                            driver.execute_script("arguments[0].click();", elem)
                            console.print(f"[green]Đã click (CSS): {css}[/green]")
                            send_clicked = True
                            time.sleep(2)
                            break
                    except Exception:
                        continue
                        
        except Exception as e:
            console.print(f"[dim]Lỗi: {e}[/dim]")
        
        if send_clicked:
            console.print("[green]✓ Đã gửi code[/green]")
        else:
            console.print("[yellow]⚠ Không click được Send code tự động[/yellow]")
        
        # Chờ và detect CAPTCHA/rate limit tự động
        console.print("[dim]Chờ xử lý (CAPTCHA nếu có)...[/dim]")
        
        for wait_time in range(30):  # Chờ tối đa 30s
            time.sleep(1)
            page_text = driver.page_source.lower()
            
            # Check rate limit
            if "maximum" in page_text and "attempts" in page_text:
                break
            
            # Check CAPTCHA đã giải xong (không còn CAPTCHA element)
            try:
                captcha_elements = driver.find_elements(By.XPATH, '//*[contains(@class, "captcha") or contains(@id, "captcha")]')
                if not captcha_elements:
                    # Không có CAPTCHA hoặc đã giải xong
                    if wait_time >= 5:  # Chờ ít nhất 5s
                        console.print("[dim]Không phát hiện CAPTCHA[/dim]")
                        break
            except Exception:
                pass
            
            if wait_time % 5 == 0:
                console.print(f"[dim]Đang chờ... {wait_time}s[/dim]")
        
        time.sleep(2)
        
        # Kiểm tra lỗi rate limit
        page_text = driver.page_source.lower()
        if "maximum" in page_text and "attempts" in page_text:
            console.print("[red]╔═══════════════════════════════════════════╗[/red]")
            console.print("[red]║  LỖI: Maximum attempts reached!           ║[/red]")
            console.print("[red]║  TikTok đã block IP của bạn.              ║[/red]")
            console.print("[red]║                                           ║[/red]")
            console.print("[red]║  Giải pháp:                               ║[/red]")
            console.print("[red]║  1. Đổi VPN/IP                            ║[/red]")
            console.print("[red]║  2. Dùng 3G/4G thay wifi                  ║[/red]")
            console.print("[red]║  3. Chờ 30 phút rồi thử lại               ║[/red]")
            console.print("[red]╚═══════════════════════════════════════════╝[/red]")
            return False
        
        # Chờ OTP từ email
        console.print("[dim]Đang chờ email OTP...[/dim]")
        otp = temp_mail.wait_for_otp(timeout=120)
        
        if not otp:
            # Thử nhập OTP thủ công
            otp = Prompt.ask("Không nhận được OTP tự động. Nhập OTP thủ công (hoặc bỏ trống để bỏ qua)")
        
        if otp:
            console.print(f"[dim]Nhập OTP: {otp}[/dim]")
            try:
                # Tìm input OTP
                otp_selectors = [
                    'input[name="code"]',
                    'input[placeholder*="code"]',
                    'input[placeholder*="Code"]',
                    'input[type="tel"]',
                    'input[maxlength="6"]',
                ]
                
                otp_input = None
                for selector in otp_selectors:
                    try:
                        otp_input = driver.find_element(By.CSS_SELECTOR, selector)
                        if otp_input.is_displayed():
                            break
                    except Exception:
                        continue
                
                if otp_input:
                    otp_input.clear()
                    for char in otp:
                        otp_input.send_keys(char)
                        time.sleep(0.1)
                    console.print("[green]Đã nhập OTP[/green]")
                else:
                    console.print("[yellow]Không tìm thấy ô nhập OTP, vui lòng nhập thủ công[/yellow]")
                    
            except Exception as e:
                console.print(f"[yellow]Lỗi nhập OTP: {e}[/yellow]")
        
        time.sleep(2)
        
        # Click đăng ký
        console.print("[dim]Click đăng ký...[/dim]")
        try:
            signup_btn = driver.find_element(By.XPATH,
                '//button[contains(text(), "Sign up")] | //button[contains(text(), "Đăng ký")] | //button[@type="submit"]'
            )
            signup_btn.click()
        except Exception:
            pass
        
        # Chờ đăng ký thành công
        console.print("[dim]Đang chờ đăng ký hoàn thành...[/dim]")
        time.sleep(10)
        
        # Kiểm tra thành công
        current_url = driver.current_url.lower()
        if "foryou" in current_url or "/@" in current_url or "profile" in current_url:
            console.print(f"[green]Đăng ký thành công![/green]")
            save_cookies(driver, temp_mail.email)
            save_account(temp_mail.email, tiktok_password)
            return True
        
        # Nếu chưa thành công, đợi thao tác thủ công
        console.print("[yellow]Chưa xác nhận thành công, có thể cần thao tác thủ công...[/yellow]")
        console.print("[dim]Hoàn thành đăng ký trong browser, rồi nhấn Enter...[/dim]")
        input()
        
        # Lưu account
        save_cookies(driver, temp_mail.email)
        save_account(temp_mail.email, tiktok_password)
        return True
        
    except Exception as e:
        console.print(f"[red]Lỗi đăng ký: {e}[/red]")
        return False
        
    finally:
        if driver:
            driver.quit()


def main():
    """Main function"""
    console.print(Panel(
        "[bold magenta]TikTok Account Generator[/bold magenta]\n"
        "[dim]Tạo tài khoản TikTok với temp mail[/dim]",
        border_style="magenta"
    ))
    
    count = Prompt.ask("Số tài khoản muốn tạo", default="1")
    
    try:
        count = int(count)
    except ValueError:
        count = 1
    
    success = 0
    failed = 0
    
    for i in range(count):
        console.print(f"\n[bold]{'='*50}[/bold]")
        console.print(f"[bold]Tạo tài khoản {i+1}/{count}[/bold]")
        
        # Tạo temp mail
        temp_mail = TempMail()
        if not temp_mail.create_account():
            console.print("[red]Không tạo được temp mail, bỏ qua...[/red]")
            failed += 1
            continue
        
        # Đăng ký TikTok
        if register_tiktok(temp_mail):
            success += 1
        else:
            failed += 1
        
        # Delay giữa các account
        if i < count - 1:
            delay = random.randint(30, 60)
            console.print(f"[dim]Chờ {delay}s trước account tiếp theo...[/dim]")
            time.sleep(delay)
    
    console.print(f"\n[bold]{'='*50}[/bold]")
    console.print(f"[bold]Kết quả:[/bold]")
    console.print(f"  [green]Thành công: {success}[/green]")
    console.print(f"  [red]Thất bại: {failed}[/red]")
    
    if success > 0:
        console.print(f"\n[dim]Accounts đã lưu vào: {ACCOUNTS_FILE}[/dim]")
        console.print(f"[dim]Cookies đã lưu vào: {COOKIES_DIR}[/dim]")
    
    # Cleanup profiles cũ
    console.print("\n[dim]Dọn dẹp profiles cũ...[/dim]")
    cleanup_old_profiles()


if __name__ == "__main__":
    main()
