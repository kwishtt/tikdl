#!/usr/bin/env python3
"""
TikTok Cookie Manager - Lấy và quản lý cookies cho các accounts

Chạy: python get_cookies.py
"""

import json
import sys
import time
import random
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
except ImportError:
    print("Cần cài đặt: pip install selenium webdriver-manager rich")
    sys.exit(1)

# ========== CONFIG ==========
console = Console()

ACCOUNTS_FILE = Path(__file__).parent / "accounts.txt"
COOKIES_DIR = Path(__file__).parent / "cookies"


# ========== FUNCTIONS ==========
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


def get_cookie_file(email: str) -> Path:
    """Lấy path file cookie của account"""
    return COOKIES_DIR / f"{email.replace('@', '_at_')}.json"


def has_cookie(email: str) -> bool:
    """Kiểm tra account đã có cookie chưa"""
    return get_cookie_file(email).exists()


def create_driver() -> webdriver.Chrome:
    """Tạo Chrome driver"""
    options = Options()
    
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
    cookie_file = get_cookie_file(email)
    save_json(cookie_file, cookies)
    console.print(f"[green]Đã lưu cookies: {cookie_file.name}[/green]")


def login_and_get_cookie(email: str, password: str) -> bool:
    """Đăng nhập và lấy cookie"""
    driver = None
    try:
        console.print(f"\n[cyan]{'='*50}[/cyan]")
        console.print(f"[bold]Đang xử lý: {email}[/bold]")
        
        driver = create_driver()
        
        # Vào trang login
        console.print("[dim]Đang mở trang đăng nhập...[/dim]")
        driver.get("https://www.tiktok.com/login/phone-or-email/email")
        time.sleep(3)
        
        # Chờ và nhập email
        wait = WebDriverWait(driver, 20)
        
        try:
            email_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[name="username"]')
            ))
        except Exception:
            console.print("[yellow]Không tìm thấy form login, thử lại...[/yellow]")
            driver.refresh()
            time.sleep(3)
            email_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[name="username"]')
            ))
        
        # Nhập email
        console.print("[dim]Nhập email...[/dim]")
        email_input.clear()
        for char in email:
            email_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(1)
        
        # Nhập password
        console.print("[dim]Nhập password...[/dim]")
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        password_input.clear()
        for char in password:
            password_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(1)
        
        # Click login
        console.print("[dim]Click login...[/dim]")
        login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_btn.click()
        
        # Chờ kết quả
        time.sleep(5)
        
        # Kiểm tra CAPTCHA
        if "captcha" in driver.current_url.lower() or "verify" in driver.page_source.lower():
            console.print("[yellow]Cần xác thực CAPTCHA/Verify![/yellow]")
            console.print("[bold]Vui lòng giải CAPTCHA trong browser...[/bold]")
            console.print("[dim]Nhấn Enter sau khi hoàn thành...[/dim]")
            input()
        
        # Chờ redirect
        console.print("[dim]Đang chờ đăng nhập...[/dim]")
        
        # Chờ tối đa 60s để login thành công
        for i in range(60):
            time.sleep(1)
            current_url = driver.current_url.lower()
            
            if "foryou" in current_url or "/@" in current_url or "profile" in current_url:
                console.print(f"[green]Đăng nhập thành công: {email}[/green]")
                save_cookies(driver, email)
                return True
            
            if i % 10 == 0 and i > 0:
                console.print(f"[dim]Đang chờ... {i}s[/dim]")
        
        # Kiểm tra lại URL cuối
        if "login" not in driver.current_url.lower():
            console.print(f"[green]Có vẻ đã login: {driver.current_url}[/green]")
            save_cookies(driver, email)
            return True
        
        console.print(f"[red]Đăng nhập thất bại: {email}[/red]")
        console.print(f"[dim]Current URL: {driver.current_url}[/dim]")
        return False
        
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/red]")
        return False
        
    finally:
        if driver:
            driver.quit()


def show_status():
    """Hiển thị trạng thái cookies"""
    accounts = load_accounts()
    
    table = Table(title="TikTok Accounts - Cookie Status")
    table.add_column("Email", style="cyan")
    table.add_column("Cookie", justify="center")
    table.add_column("Cookie File", style="dim")
    
    for acc in accounts:
        email = acc["email"]
        has = has_cookie(email)
        status = "[green]Có[/green]" if has else "[red]Chưa có[/red]"
        file_name = get_cookie_file(email).name if has else "-"
        table.add_row(email, status, file_name)
    
    console.print(table)
    
    # Thống kê
    total = len(accounts)
    with_cookie = sum(1 for acc in accounts if has_cookie(acc["email"]))
    console.print(f"\n[bold]Tổng:[/bold] {with_cookie}/{total} accounts có cookie")


def get_missing_cookies():
    """Lấy cookies cho các accounts chưa có"""
    accounts = load_accounts()
    
    # Lọc accounts chưa có cookie
    missing = [acc for acc in accounts if not has_cookie(acc["email"])]
    
    if not missing:
        console.print("[green]Tất cả accounts đã có cookie![/green]")
        return
    
    console.print(f"[bold]Có {len(missing)} accounts chưa có cookie:[/bold]")
    for acc in missing:
        console.print(f"  - {acc['email']}")
    
    console.print()
    confirm = Prompt.ask("Bắt đầu lấy cookies?", choices=["y", "n"], default="y")
    
    if confirm.lower() != "y":
        return
    
    success = 0
    failed = 0
    
    for acc in missing:
        if login_and_get_cookie(acc["email"], acc["password"]):
            success += 1
        else:
            failed += 1
        
        # Delay giữa các account
        if acc != missing[-1]:
            delay = random.randint(5, 15)
            console.print(f"[dim]Chờ {delay}s trước account tiếp theo...[/dim]")
            time.sleep(delay)
    
    console.print(f"\n[bold]Kết quả:[/bold]")
    console.print(f"  [green]Thành công: {success}[/green]")
    console.print(f"  [red]Thất bại: {failed}[/red]")


def get_single_cookie():
    """Lấy cookie cho 1 account cụ thể"""
    email = Prompt.ask("Nhập email")
    
    accounts = load_accounts()
    acc = next((a for a in accounts if a["email"] == email), None)
    
    if not acc:
        console.print(f"[red]Không tìm thấy account: {email}[/red]")
        return
    
    if has_cookie(email):
        overwrite = Prompt.ask("Account đã có cookie, ghi đè?", choices=["y", "n"], default="n")
        if overwrite.lower() != "y":
            return
    
    login_and_get_cookie(acc["email"], acc["password"])


def delete_cookie():
    """Xóa cookie của 1 account"""
    email = Prompt.ask("Nhập email để xóa cookie")
    
    cookie_file = get_cookie_file(email)
    if cookie_file.exists():
        cookie_file.unlink()
        console.print(f"[green]Đã xóa cookie: {email}[/green]")
    else:
        console.print(f"[yellow]Không tìm thấy cookie: {email}[/yellow]")


def main():
    """Main function"""
    console.print(Panel(
        "[bold magenta]TikTok Cookie Manager[/bold magenta]\n"
        "[dim]Quản lý cookies cho auto_post.py[/dim]",
        border_style="magenta"
    ))
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "status":
            show_status()
        elif cmd == "get":
            get_missing_cookies()
        elif cmd == "single":
            get_single_cookie()
        elif cmd == "delete":
            delete_cookie()
        else:
            console.print(f"[red]Lệnh không hợp lệ: {cmd}[/red]")
    else:
        console.print("\n[bold]Cách dùng:[/bold]")
        console.print("  python get_cookies.py status  - Xem trạng thái cookies")
        console.print("  python get_cookies.py get     - Lấy cookies cho accounts chưa có")
        console.print("  python get_cookies.py single  - Lấy cookie cho 1 account")
        console.print("  python get_cookies.py delete  - Xóa cookie của 1 account")
        
        console.print("\n[bold]Menu:[/bold]")
        choice = Prompt.ask("Chọn", choices=["1", "2", "3", "4"], default="1")
        
        if choice == "1":
            show_status()
        elif choice == "2":
            get_missing_cookies()
        elif choice == "3":
            get_single_cookie()
        elif choice == "4":
            delete_cookie()


if __name__ == "__main__":
    main()
