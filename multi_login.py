#!/usr/bin/env python3
"""
TikTok Multi-Account Manager - Mở nhiều accounts cùng lúc

Chạy: python multi_login.py
"""

import json
import sys
import time
import random
import threading
from pathlib import Path
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
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

COOKIES_DIR = Path(__file__).parent / "cookies"
PROFILES_DIR = Path(__file__).parent / "chrome_profiles"

# ========== FUNCTIONS ==========
def get_available_accounts() -> list[dict]:
    """Lấy danh sách accounts có cookies"""
    accounts = []
    
    if not COOKIES_DIR.exists():
        return accounts
    
    for cookie_file in COOKIES_DIR.glob("*.json"):
        # Chuyển tên file thành email
        email = cookie_file.stem.replace("_at_", "@")
        accounts.append({
            "email": email,
            "cookie_file": cookie_file
        })
    
    return accounts


def get_screen_size() -> tuple:
    """Lấy kích thước màn hình"""
    # Mặc định
    return 1920, 1080


def calculate_window_positions(num_windows: int, screen_width: int = 1920, screen_height: int = 1080) -> list[dict]:
    """Tính toán vị trí các cửa sổ để sắp xếp cân bằng"""
    positions = []
    
    if num_windows == 1:
        # 1 cửa sổ - full màn hình
        positions.append({
            "x": 0, "y": 0,
            "width": screen_width, "height": screen_height
        })
    elif num_windows == 2:
        # 2 cửa sổ - chia đôi ngang
        w = screen_width // 2
        positions.append({"x": 0, "y": 0, "width": w, "height": screen_height})
        positions.append({"x": w, "y": 0, "width": w, "height": screen_height})
    elif num_windows == 3:
        # 3 cửa sổ - 2 trên, 1 dưới
        w = screen_width // 2
        h = screen_height // 2
        positions.append({"x": 0, "y": 0, "width": w, "height": h})
        positions.append({"x": w, "y": 0, "width": w, "height": h})
        positions.append({"x": screen_width // 4, "y": h, "width": w, "height": h})
    elif num_windows == 4:
        # 4 cửa sổ - grid 2x2
        w = screen_width // 2
        h = screen_height // 2
        positions.append({"x": 0, "y": 0, "width": w, "height": h})
        positions.append({"x": w, "y": 0, "width": w, "height": h})
        positions.append({"x": 0, "y": h, "width": w, "height": h})
        positions.append({"x": w, "y": h, "width": w, "height": h})
    elif num_windows <= 6:
        # 5-6 cửa sổ - grid 3x2
        w = screen_width // 3
        h = screen_height // 2
        for i in range(num_windows):
            row = i // 3
            col = i % 3
            positions.append({"x": col * w, "y": row * h, "width": w, "height": h})
    elif num_windows <= 9:
        # 7-9 cửa sổ - grid 3x3
        w = screen_width // 3
        h = screen_height // 3
        for i in range(num_windows):
            row = i // 3
            col = i % 3
            positions.append({"x": col * w, "y": row * h, "width": w, "height": h})
    else:
        # 10+ cửa sổ - grid 4x3
        w = screen_width // 4
        h = screen_height // 3
        for i in range(num_windows):
            row = i // 4
            col = i % 4
            positions.append({"x": col * w, "y": row * h, "width": w, "height": h})
    
    return positions


def create_driver_for_account(email: str, position: dict) -> Optional[webdriver.Chrome]:
    """Tạo Chrome driver cho 1 account với profile riêng"""
    options = Options()
    
    # Profile riêng cho mỗi account
    profile_name = f"account_{email.replace('@', '_at_').replace('.', '_')}"
    profile_path = PROFILES_DIR / profile_name
    profile_path.mkdir(parents=True, exist_ok=True)
    
    options.add_argument(f"--user-data-dir={profile_path}")
    
    # Window size và position
    options.add_argument(f"--window-size={position['width']},{position['height']}")
    options.add_argument(f"--window-position={position['x']},{position['y']}")
    
    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set window position và size
        driver.set_window_position(position["x"], position["y"])
        driver.set_window_size(position["width"], position["height"])
        
        # Override webdriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        console.print(f"[red]Lỗi tạo driver cho {email}: {e}[/red]")
        return None


def load_cookies(driver: webdriver.Chrome, cookie_file: Path) -> bool:
    """Load cookies vào browser"""
    try:
        # Vào TikTok trước để set domain
        driver.get("https://www.tiktok.com")
        time.sleep(2)
        
        # Load cookies
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        
        for cookie in cookies:
            try:
                # Xóa các field không cần thiết
                if "sameSite" in cookie:
                    if cookie["sameSite"] == "None":
                        cookie["sameSite"] = "Strict"
                if "expiry" in cookie:
                    cookie["expiry"] = int(cookie["expiry"])
                
                driver.add_cookie(cookie)
            except Exception:
                continue
        
        return True
    except Exception as e:
        console.print(f"[red]Lỗi load cookies: {e}[/red]")
        return False


def login_account(email: str, cookie_file: Path, position: dict, drivers: list, lock: threading.Lock):
    """Login 1 account trong thread riêng"""
    console.print(f"[cyan]Đang mở: {email}[/cyan]")
    
    driver = create_driver_for_account(email, position)
    if not driver:
        return
    
    # Load cookies
    if load_cookies(driver, cookie_file):
        # Refresh để apply cookies
        driver.get("https://www.tiktok.com/foryou")
        time.sleep(2)
        
        console.print(f"[green]✓ Đã mở: {email}[/green]")
    else:
        console.print(f"[yellow]⚠ Có thể chưa login: {email}[/yellow]")
    
    with lock:
        drivers.append({"email": email, "driver": driver})


def show_accounts():
    """Hiển thị danh sách accounts có cookies"""
    accounts = get_available_accounts()
    
    if not accounts:
        console.print("[yellow]Không có accounts nào có cookies![/yellow]")
        console.print(f"[dim]Đường dẫn cookies: {COOKIES_DIR}[/dim]")
        return
    
    table = Table(title="TikTok Accounts (có cookies)")
    table.add_column("#", justify="center", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Cookie File", style="dim")
    
    for i, acc in enumerate(accounts, 1):
        table.add_row(str(i), acc["email"], acc["cookie_file"].name)
    
    console.print(table)
    console.print(f"\n[bold]Tổng: {len(accounts)} accounts[/bold]")


def open_accounts():
    """Mở nhiều accounts cùng lúc"""
    accounts = get_available_accounts()
    
    if not accounts:
        console.print("[yellow]Không có accounts nào có cookies![/yellow]")
        return
    
    # Hiển thị accounts
    show_accounts()
    
    # Chọn accounts
    console.print("\n[bold]Chọn accounts để mở:[/bold]")
    console.print("  - Nhập 'all' để mở tất cả")
    console.print("  - Nhập số (VD: 1,2,3 hoặc 1-5)")
    
    selection = Prompt.ask("Chọn", default="all")
    
    # Parse selection
    selected_accounts = []
    if selection.lower() == "all":
        selected_accounts = accounts
    else:
        try:
            for part in selection.split(","):
                if "-" in part:
                    start, end = part.split("-")
                    for i in range(int(start), int(end) + 1):
                        if 1 <= i <= len(accounts):
                            selected_accounts.append(accounts[i - 1])
                else:
                    idx = int(part)
                    if 1 <= idx <= len(accounts):
                        selected_accounts.append(accounts[idx - 1])
        except Exception:
            console.print("[red]Lỗi parse selection[/red]")
            return
    
    if not selected_accounts:
        console.print("[yellow]Không có accounts nào được chọn![/yellow]")
        return
    
    console.print(f"\n[bold]Sẽ mở {len(selected_accounts)} accounts[/bold]")
    
    # Tính toán vị trí cửa sổ
    positions = calculate_window_positions(len(selected_accounts))
    
    # Mở các accounts
    drivers = []
    lock = threading.Lock()
    threads = []
    
    console.print("\n[dim]Đang mở các browsers...[/dim]")
    
    for i, acc in enumerate(selected_accounts):
        thread = threading.Thread(
            target=login_account,
            args=(acc["email"], acc["cookie_file"], positions[i], drivers, lock)
        )
        threads.append(thread)
        thread.start()
        
        # Delay nhẹ để tránh conflict
        time.sleep(0.5)
    
    # Chờ tất cả threads hoàn thành
    for thread in threads:
        thread.join()
    
    console.print(f"\n[bold green]Đã mở {len(drivers)} accounts![/bold green]")
    
    # Menu điều khiển
    console.print("\n[bold]Điều khiển:[/bold]")
    console.print("  q - Đóng tất cả browsers")
    console.print("  r - Refresh tất cả")
    console.print("  Ctrl+C - Thoát (giữ browsers mở)")
    
    try:
        while True:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "q":
                console.print("[dim]Đang đóng tất cả browsers...[/dim]")
                for d in drivers:
                    try:
                        d["driver"].quit()
                    except Exception:
                        pass
                console.print("[green]Đã đóng tất cả![/green]")
                break
            
            elif cmd == "r":
                console.print("[dim]Đang refresh tất cả...[/dim]")
                for d in drivers:
                    try:
                        d["driver"].refresh()
                    except Exception:
                        pass
                console.print("[green]Đã refresh![/green]")
            
    except KeyboardInterrupt:
        console.print("\n[dim]Thoát (browsers vẫn mở)[/dim]")


def main():
    """Main function"""
    console.print(Panel(
        "[bold magenta]TikTok Multi-Account Manager[/bold magenta]\n"
        "[dim]Mở nhiều accounts TikTok cùng lúc[/dim]",
        border_style="magenta"
    ))
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "list":
            show_accounts()
        elif cmd == "open":
            open_accounts()
        else:
            console.print(f"[red]Lệnh không hợp lệ: {cmd}[/red]")
    else:
        console.print("\n[bold]Menu:[/bold]")
        console.print("  1. Xem danh sách accounts")
        console.print("  2. Mở nhiều accounts")
        
        choice = Prompt.ask("Chọn", choices=["1", "2"], default="2")
        
        if choice == "1":
            show_accounts()
        elif choice == "2":
            open_accounts()


if __name__ == "__main__":
    main()
