"""TikTok video link scraper using Playwright chromium-headless-shell."""

import asyncio
import logging
import urllib.parse
from typing import List, Optional

logger = logging.getLogger(__name__)


def crawl_tiktok_links(
    query: str,
    scroll_count: int = 3,
    headless: bool = True,
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> List[str]:
    """Extract list of TikTok video URLs matching a search query.

    Args:
        query: Search query string (required).
        scroll_count: Number of page scroll actions to load more videos (default: 3).
        headless: Run headless browser with chromium-headless-shell (default: True).
        output_file: Optional file path to persist results.
        verbose: Print progress log messages (default: True).

    Returns:
        List of unique cleaned TikTok video URLs.
    """
    if not query or not str(query).strip():
        raise ValueError("Lỗi: Chuỗi query tìm kiếm không được để trống!")

    def log(msg: str) -> None:
        if verbose:
            logger.info(msg)

    clean_query = str(query).strip()
    encoded_query = urllib.parse.quote(clean_query)
    search_url = f"https://www.tiktok.com/search?q={encoded_query}"

    links: List[str] = []
    log(f"[*] [TikTok Crawler] Bắt đầu tìm kiếm với từ khóa: '{clean_query}'")
    log(f"[*] [TikTok Crawler] Trình duyệt: chromium-headless-shell | Headless: {headless} | Scrolls: {scroll_count}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "[!] Thư viện playwright chưa được cài đặt. Hãy chạy: pip install playwright && playwright install chromium"
        )
        return []

    try:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
            try:
                browser = p.chromium.launch(
                    channel="chromium-headless-shell",
                    headless=headless,
                    args=launch_args,
                )
            except Exception:
                # Fallback to standard chromium if chromium-headless-shell is not installed
                browser = p.chromium.launch(
                    headless=headless,
                    args=launch_args,
                )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="vi-VN",
            )

            page = context.new_page()

            # Hide automation flag navigator.webdriver
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                # Step 1: Session warmup to receive cookies & session tokens from TikTok
                log("[*] [TikTok Crawler] Khởi tạo phiên làm việc với TikTok (Session Warmup)...")
                page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)

                # Close login modal if present
                try:
                    close_btn = page.query_selector(
                        '[data-e2e="modal-close-inner-button"], div[aria-label="Close"]'
                    )
                    if close_btn:
                        close_btn.click()
                except Exception:
                    pass

                # Step 2: Navigate to search URL
                log(f"[*] [TikTok Crawler] Điều hướng tới: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3500)

                # Check for temporary network error retry button
                retry_btn = page.query_selector(
                    'button:has-text("Try again"), button:has-text("Thử lại"), button:has-text("もう一度お試しください")'
                )
                if retry_btn:
                    log("[*] [TikTok Crawler] Nhấn nút 'Thử lại' do TikTok yêu cầu...")
                    retry_btn.click()
                    page.wait_for_timeout(4000)

                # Step 3: Scroll down to load more video items
                for i in range(scroll_count):
                    log(f"[*] [TikTok Crawler] Đang cuộn trang lần {i + 1}/{scroll_count}...")
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(2500)

                # Step 4: Extract all video anchor links and clean tracking params
                hrefs = page.eval_on_selector_all(
                    'a[href*="/video/"]',
                    "elements => elements.map(el => el.href.split('?')[0])",
                )

                # Deduplicate while preserving order
                links = list(dict.fromkeys(hrefs))
                log(f"[+] [TikTok Crawler] Hoàn tất! Tìm thấy tổng cộng: {len(links)} link video.")

            except Exception as e:
                logger.warning(f"[!] [TikTok Crawler] Lỗi khi cào dữ liệu cho '{clean_query}': {e}")
            finally:
                context.close()
                browser.close()

    except Exception as e:
        logger.warning(f"[!] [TikTok Crawler] Không thể khởi chạy trình duyệt Playwright: {e}")

    # Optionally persist to file
    if output_file and links:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link}\n")
            log(f"[+] [TikTok Crawler] Đã lưu danh sách vào file: {output_file}")
        except Exception as e:
            logger.warning(f"[!] [TikTok Crawler] Không thể ghi file {output_file}: {e}")

    return links


async def crawl_tiktok_links_async(
    query: str,
    scroll_count: int = 3,
    headless: bool = True,
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> List[str]:
    """Asynchronous wrapper for crawl_tiktok_links to prevent blocking the asyncio event loop."""
    return await asyncio.to_thread(
        crawl_tiktok_links,
        query=query,
        scroll_count=scroll_count,
        headless=headless,
        output_file=output_file,
        verbose=verbose,
    )

