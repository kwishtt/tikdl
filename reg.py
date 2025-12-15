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


# ========== SELENIUM FUNCTIONS ==========
def create_driver() -> webdriver.Chrome:
    """Tạo Chrome driver"""
    options = Options()
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
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
    """Tạo password ngẫu nhiên"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choices(chars, k=12))


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
        time.sleep(3)
        
        # Chọn ngày sinh
        console.print("[dim]Chọn ngày sinh...[/dim]")
        year, month, day = random_birthday()
        
        try:
            # Month
            month_select = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'select[placeholder="Month"], [data-e2e="month-select"]')
            ))
            month_select.click()
            time.sleep(0.5)
            month_option = driver.find_element(By.XPATH, f'//option[@value="{month}"]')
            month_option.click()
            
            # Day
            day_select = driver.find_element(By.CSS_SELECTOR, 'select[placeholder="Day"], [data-e2e="day-select"]')
            day_select.click()
            time.sleep(0.5)
            day_option = driver.find_element(By.XPATH, f'//option[@value="{day}"]')
            day_option.click()
            
            # Year
            year_select = driver.find_element(By.CSS_SELECTOR, 'select[placeholder="Year"], [data-e2e="year-select"]')
            year_select.click()
            time.sleep(0.5)
            year_option = driver.find_element(By.XPATH, f'//option[@value="{year}"]')
            year_option.click()
            
        except Exception as e:
            console.print(f"[yellow]Lỗi chọn ngày sinh: {e}[/yellow]")
            console.print("[yellow]Vui lòng chọn ngày sinh thủ công...[/yellow]")
            input("Nhấn Enter sau khi chọn xong...")
        
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
        
        time.sleep(1)
        
        # Click gửi code
        console.print("[dim]Click gửi mã xác thực...[/dim]")
        try:
            send_code_btn = driver.find_element(By.XPATH, 
                '//button[contains(text(), "Send code")] | //button[contains(text(), "Gửi mã")]'
            )
            send_code_btn.click()
        except Exception:
            console.print("[yellow]Không tìm thấy nút Send code, thử click Next...[/yellow]")
            try:
                next_btn = driver.find_element(By.XPATH, '//button[contains(text(), "Next")]')
                next_btn.click()
            except Exception:
                pass
        
        time.sleep(3)
        
        # Kiểm tra CAPTCHA
        if "captcha" in driver.page_source.lower():
            console.print("[yellow]Có CAPTCHA - Vui lòng giải thủ công![/yellow]")
            input("Nhấn Enter sau khi giải xong CAPTCHA...")
        
        # Chờ OTP từ email
        otp = temp_mail.wait_for_otp(timeout=120)
        
        if not otp:
            # Thử nhập OTP thủ công
            otp = Prompt.ask("Nhập OTP thủ công (nếu có)")
        
        if otp:
            console.print(f"[dim]Nhập OTP: {otp}[/dim]")
            try:
                otp_input = driver.find_element(By.CSS_SELECTOR, 
                    'input[name="code"], input[placeholder*="code"], input[placeholder*="mã"]'
                )
                otp_input.clear()
                for char in otp:
                    otp_input.send_keys(char)
                    time.sleep(0.1)
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


if __name__ == "__main__":
    main()
