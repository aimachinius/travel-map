import argparse
import sys
import urllib.parse
from playwright.sync_api import sync_playwright

def crawl_tiktok_links(
    query: str, 
    scroll_count: int = 3, 
    headless: bool = True,
    output_file: str = None,
    verbose: bool = True
) -> list[str]:
    """
    Trích xuất danh sách link video TikTok theo từ khóa tìm kiếm.

    :param query: Chuỗi từ khóa tìm kiếm (bắt buộc)
    :param scroll_count: Số lần cuộn trang để tải thêm video (mặc định: 3)
    :param headless: Chạy trình duyệt ẩn danh với chromium-headless-shell (mặc định: True)
    :param output_file: Đường dẫn file để ghi kết quả (tùy chọn)
    :param verbose: In log tiến trình ra màn hình (mặc định: True)
    :return: Danh sách các URL video TikTok duy nhất
    """
    if not query or not str(query).strip():
        raise ValueError("Lỗi: Chuỗi query tìm kiếm không được để trống!")

    def log(msg: str):
        if verbose:
            print(msg)

    clean_query = str(query).strip()
    encoded_query = urllib.parse.quote(clean_query)
    search_url = f"https://www.tiktok.com/search?q={encoded_query}"

    links = []
    log(f"[*] Bắt đầu tìm kiếm với từ khóa: '{clean_query}'")
    log(f"[*] Trình duyệt: chromium-headless-shell | Headless: {headless}")
    log(f"[*] Số lần cuộn trang: {scroll_count}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chromium-headless-shell",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="vi-VN"
        )

        page = context.new_page()

        # Ẩn cờ tự động hóa navigator.webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        try:
            # Bước 1: Khởi tạo phiên duyệt web để nhận session token & cookies từ TikTok
            log("[*] Đang khởi tạo phiên làm việc với TikTok...")
            page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            # Đóng banner đăng nhập nếu xuất hiện
            try:
                close_btn = page.query_selector('[data-e2e="modal-close-inner-button"], div[aria-label="Close"]')
                if close_btn:
                    close_btn.click()
            except Exception:
                pass

            # Bước 2: Truy cập trang tìm kiếm với từ khóa
            log(f"[*] Điều hướng tới: {search_url}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3500)

            # Kiểm tra nếu xuất hiện nút 'Thử lại' do lỗi mạng tạm thời
            retry_btn = page.query_selector(
                'button:has-text("Try again"), button:has-text("Thử lại"), button:has-text("もう一度お試しください")'
            )
            if retry_btn:
                log("[*] Nhấn thử lại...")
                retry_btn.click()
                page.wait_for_timeout(4000)

            # Bước 3: Cuộn trang để tải thêm danh sách video
            for i in range(scroll_count):
                log(f"[*] Đang cuộn trang lần {i + 1}/{scroll_count}...")
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2500)

            # Bước 4: Trích xuất tất cả các thẻ <a> chứa link video
            hrefs = page.eval_on_selector_all(
                'a[href*="/video/"]', 
                "elements => elements.map(el => el.href.split('?')[0])"
            )

            # Loại bỏ link trùng lặp
            links = list(dict.fromkeys(hrefs))
            log(f"[+] Hoàn tất! Tìm thấy tổng cộng: {len(links)} link video.")

        except Exception as e:
            log(f"[!] Lỗi khi cào dữ liệu: {e}")
            raise e
        finally:
            context.close()
            browser.close()

    # Ghi ra file nếu có yêu cầu
    if output_file and links:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link}\n")
            log(f"[+] Đã lưu danh sách vào file: {output_file}")
        except Exception as e:
            log(f"[!] Không thể ghi file {output_file}: {e}")

    return links

def main():
    parser = argparse.ArgumentParser(
        description="Script trích xuất danh sách link video TikTok theo từ khóa tìm kiếm (query)."
    )
    parser.add_argument(
        "query", 
        type=str, 
        nargs="?",
        default=None,
        help="Từ khóa tìm kiếm trên TikTok (ví dụ: 'ẩm thực việt nam')"
    )
    parser.add_argument(
        "-s", "--scroll", 
        type=int, 
        default=3, 
        help="Số lần cuộn trang để tải thêm video (mặc định: 3)"
    )
    parser.add_argument(
        "--headed", 
        action="store_true", 
        help="Mở giao diện cửa sổ (mặc định: chạy headless shell)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default=None, 
        help="Đường dẫn file văn bản (.txt) để lưu danh sách link"
    )

    args = parser.parse_args()

    # Nếu người dùng không nhập query qua CLI, yêu cầu nhập từ bàn phím
    query = args.query
    if not query:
        try:
            query = input("Nhập từ khóa tìm kiếm TikTok: ").strip()
        except EOFError:
            pass

    if not query:
        print("[!] Lỗi: Bạn chưa cung cấp từ khóa tìm kiếm (query).")
        sys.exit(1)

    results = crawl_tiktok_links(
        query=query, 
        scroll_count=args.scroll, 
        headless=not args.headed,
        output_file=args.output
    )

    print("\n--- KẾT QUẢ LINK VIDEO TRÍCH XUẤT ---")
    for idx, link in enumerate(results, 1):
        print(f"{idx}. {link}")

if __name__ == "__main__":
    main()
