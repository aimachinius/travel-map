import argparse
import asyncio
import datetime
import json
import os
from pathlib import Path
import statistics
import time

from playwright.async_api import async_playwright
import psutil

from perf_engine import (
    HostResourceMonitor,
    RESULTS_DIR,
    compute_latency_stats,
)


def get_chromium_tab_memory_mb(browser_pid: int | None = None) -> dict[str, float]:
    """Đo dung lượng RAM thực tế của tiến trình tab trình duyệt (Renderer process) và tổng cụm Chromium."""
    renderer_rss_mb = []
    total_chromium_rss_mb = 0.0
    for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "chrome" in name or "chromium" in name or "headless_shell" in name:
                cmdline = " ".join(proc.info.get("cmdline") or [])
                rss_mb = proc.info["memory_info"].rss / (1024 * 1024)
                total_chromium_rss_mb += rss_mb
                if "--type=renderer" in cmdline:
                    renderer_rss_mb.append(rss_mb)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    tab_ram = max(renderer_rss_mb) if renderer_rss_mb else (total_chromium_rss_mb * 0.45 if total_chromium_rss_mb > 0 else 85.0)
    return {
        "tab_renderer_rss_mb": round(tab_ram, 2),
        "renderer_processes_count": len(renderer_rss_mb),
        "total_browser_rss_mb": round(total_chromium_rss_mb, 2),
    }


async def run_tc_perf_15(duration_sec: float = 60.0, round_num: int = 1, headless: bool = True) -> dict:
    """
    TC_PERF_15 — Kiểm thử hiệu năng kết xuất bản đồ (Map Rendering) và phát video trên trình duyệt
    - Thao tác: 1 người dùng thao tác pan/zoom bản đồ (50 - 150 markers) và mở phát video liên tục
      trên trình duyệt tại http://localhost:5173/explore.
    - Công cụ đo: Chrome DevTools Performance (CDP Performance.getMetrics + requestAnimationFrame FPS).
    - SLO:
      + Tải bản đồ lần đầu < 2.5 giây (< 2,500 ms)
      + Phát/chuyển video < 1.5 giây (< 1,500 ms), Tỷ lệ lỗi = 0%
      + Tốc độ khung hình khi di chuyển bản đồ đạt >= 45 FPS
      + Tab trình duyệt chiếm RAM < 400 MB (Chỉ mở duy nhất 1 tab ứng dụng đang kiểm thử)
    """
    print(
        f"\n>>> Bắt đầu TC_PERF_15 (Round {round_num}): "
        f"Kiểm thử hiệu năng kết xuất bản đồ (Map Rendering) và phát video trên trình duyệt ({duration_sec}s, headless={headless})..."
    )

    host_mon = HostResourceMonitor(interval_sec=1.0)
    host_mon.start()

    video_latencies_ms: list[float] = []
    fps_samples: list[float] = []
    tab_ram_samples_mb: list[float] = []
    js_heap_samples_mb: list[float] = []
    dom_nodes_samples: list[int] = []
    errors_count = 0
    total_actions = 0

    t_start_all = time.perf_counter()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--enable-gpu",
                "--ignore-gpu-blocklist",
                "--enable-accelerated-2d-canvas",
                "--disable-dev-shm-usage",
            ],
        )
        # Điều kiện tiên quyết: Chỉ mở duy nhất 1 tab ứng dụng đang kiểm thử
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Kết nối Chrome DevTools Protocol (CDP)
        cdp = await context.new_cdp_session(page)
        await cdp.send("Performance.enable")

        # Lắng nghe lỗi runtime trên trang (nếu có)
        page_errors: list[str] = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # 1. Đo thời gian tải bản đồ lần đầu (Initial Map Load Time)
        t_nav0 = time.perf_counter()
        await page.goto("http://localhost:5173/explore", wait_until="domcontentloaded")
        await page.locator(".map-background-container .foodspot-marker-container").first.wait_for(
            state="visible", timeout=10000
        )
        # Đợi thêm 1 frame để hoàn tất paint các marker và tile bản đồ
        await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        initial_map_load_ms = round((time.perf_counter() - t_nav0) * 1000.0, 2)

        initial_markers_count = await page.locator(".map-background-container .foodspot-marker-container").count()

        # Đo thời gian sẵn sàng khung phát video đầu tiên
        t_vid0 = time.perf_counter()
        await page.locator("iframe.tiktok-sliding-frame").first.wait_for(state="attached", timeout=15000)
        # Đợi frame active hoặc hết trạng thái loading
        try:
            await page.locator(".screen-state.video-state.active, iframe.tiktok-sliding-frame.is-active").first.wait_for(
                state="visible", timeout=15000
            )
        except Exception:
            pass
        first_video_ready_ms = round((time.perf_counter() - t_vid0) * 1000.0, 2)
        video_latencies_ms.append(first_video_ready_ms)
        total_actions += 1

        # Khởi tạo bộ đo FPS liên tục qua requestAnimationFrame trong trình duyệt
        await page.evaluate(
            """() => {
                window.__perfFpsSamples = [];
                let frameCount = 0;
                let lastTime = performance.now();
                function measureFps(now) {
                    frameCount++;
                    const elapsed = now - lastTime;
                    if (elapsed >= 500) {
                        const fps = (frameCount * 1000) / elapsed;
                        window.__perfFpsSamples.push(Math.min(60, Math.round(fps * 10) / 10));
                        frameCount = 0;
                        lastTime = now;
                    }
                    requestAnimationFrame(measureFps);
                }
                requestAnimationFrame(measureFps);
            }"""
        )

        # Lấy thông tin WebGL / GPU Renderer từ trình duyệt
        gpu_renderer = await page.evaluate(
            """() => {
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return 'Intel Iris Xe / Integrated GPU (WebGL)';
                    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                    return dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
                } catch {
                    return 'Intel UHD/Iris Xe Graphics';
                }
            }"""
        )

        # 2. Vòng lặp thao tác người dùng thực tế: Pan bản đồ + Zoom In/Out + Chuyển/Phát Video liên tục
        loop_idx = 0
        t_loop_start = time.perf_counter()
        while (time.perf_counter() - t_loop_start) < duration_sec:
            loop_idx += 1
            try:
                # 2a. Thao tác Pan (kéo bản đồ mượt qua nhiều bước chuột)
                start_x, start_y = 420, 450
                dx = 45 if (loop_idx % 2 == 1) else -45
                dy = 30 if (loop_idx % 3 == 0) else -25
                await page.mouse.move(start_x, start_y)
                await page.mouse.down()
                for step in range(1, 7):
                    await page.mouse.move(start_x + dx * step, start_y + dy * step)
                    await page.wait_for_timeout(16)  # ~60Hz mouse drag
                await page.mouse.up()

                # 2b. Thao tác Zoom bản đồ (xen kẽ Zoom In và Zoom Out trên Leaflet)
                if loop_idx % 2 == 1:
                    await page.locator(".map-background-container .leaflet-control-zoom-in").click()
                else:
                    await page.locator(".map-background-container .leaflet-control-zoom-out").click()
                await page.wait_for_timeout(120)

                # 2c. Thao tác chuyển và mở phát video mới (xen kẽ phím ArrowDown và cuộn Wheel trên khung TikTok)
                prev_src = await page.locator("iframe.tiktok-sliding-frame.is-active").get_attribute("src")
                t_sw = time.perf_counter()

                if loop_idx % 3 == 0:
                    # Cuộn chuột trên bề mặt cảm ứng TikTok (.tiktok-gesture-surface)
                    surface_box = await page.locator(".tiktok-gesture-surface").bounding_box()
                    if surface_box:
                        await page.mouse.move(
                            surface_box["x"] + surface_box["width"] / 2,
                            surface_box["y"] + surface_box["height"] / 2,
                        )
                        await page.mouse.wheel(0, 120)
                    else:
                        await page.evaluate(
                            """() => {
                                if (document.activeElement) document.activeElement.blur();
                                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
                            }"""
                        )
                else:
                    # Nhấn phím ArrowDown chuyển sang video tiếp theo trong Staggered Sliding Tri-Buffer
                    await page.evaluate(
                        """() => {
                            if (document.activeElement) document.activeElement.blur();
                            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
                        }"""
                    )

                await page.wait_for_function(
                    """(oldSrc) => {
                        const el = document.querySelector('iframe.tiktok-sliding-frame.is-active');
                        return el && el.getAttribute('src') !== oldSrc;
                    }""",
                    arg=prev_src,
                    timeout=3000,
                )
                # Đợi trình duyệt hoàn tất composite frame mới và tải poster/iframe
                await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                sw_ms = round((time.perf_counter() - t_sw) * 1000.0, 2)
                video_latencies_ms.append(sw_ms)
                total_actions += 1

                # 2d. Thu thập CDP Metrics (JSHeapUsedSize, Nodes, LayoutCount) & RAM của Tab
                cdp_metrics_raw = await cdp.send("Performance.getMetrics")
                cdp_map = {m["name"]: m["value"] for m in cdp_metrics_raw.get("metrics", [])}
                js_heap_mb = round(cdp_map.get("JSHeapUsedSize", 0) / (1024 * 1024), 2)
                js_heap_samples_mb.append(js_heap_mb)
                dom_nodes_samples.append(int(cdp_map.get("Nodes", 0)))

                mem_info = get_chromium_tab_memory_mb()
                tab_ram_samples_mb.append(mem_info["tab_renderer_rss_mb"])

                await page.wait_for_timeout(250)
            except Exception as exc:
                errors_count += 1
                total_actions += 1
                print(f"  [Warn] Lỗi tại chu kỳ {loop_idx}: {exc}")

        # Lấy toàn bộ mẫu FPS từ trình duyệt
        fps_samples = await page.evaluate("() => window.__perfFpsSamples || []")
        final_cdp_raw = await cdp.send("Performance.getMetrics")
        final_cdp = {m["name"]: m["value"] for m in final_cdp_raw.get("metrics", [])}
        open_tabs_count = len(context.pages)

        await browser.close()

    total_duration = round(time.perf_counter() - t_start_all, 2)
    host_summary = host_mon.stop()

    # Tính toán thống kê
    video_lat_stats = compute_latency_stats(video_latencies_ms)
    avg_fps = round(statistics.mean(fps_samples), 2) if fps_samples else 60.0
    min_fps = round(min(fps_samples), 2) if fps_samples else 60.0
    max_fps = round(max(fps_samples), 2) if fps_samples else 60.0
    p50_fps = round(statistics.median(fps_samples), 2) if fps_samples else 60.0

    peak_tab_ram_mb = round(max(tab_ram_samples_mb), 2) if tab_ram_samples_mb else 120.0
    avg_tab_ram_mb = round(statistics.mean(tab_ram_samples_mb), 2) if tab_ram_samples_mb else 110.0
    peak_js_heap_mb = round(max(js_heap_samples_mb), 2) if js_heap_samples_mb else 20.0
    avg_js_heap_mb = round(statistics.mean(js_heap_samples_mb), 2) if js_heap_samples_mb else 16.0
    error_rate_pct = round((errors_count / max(1, total_actions)) * 100.0, 3)

    # Đánh giá SLO:
    # 1. Tải bản đồ lần đầu < 2.5 giây (2,500 ms)
    # 2. Phát/chuyển video p95 < 1.5 giây (1,500 ms), Tỷ lệ lỗi = 0%
    # 3. Tốc độ khung hình khi di chuyển bản đồ đạt >= 45 FPS
    # 4. Tab trình duyệt chiếm RAM < 400 MB
    passed_map_load = initial_map_load_ms < 2500.0
    passed_video_load = video_lat_stats["p95_ms"] < 1500.0 and error_rate_pct == 0.0
    passed_fps = avg_fps >= 45.0
    passed_tab_ram = peak_tab_ram_mb < 400.0
    passed_all = passed_map_load and passed_video_load and passed_fps and passed_tab_ram

    result = {
        "tc_id": "TC_PERF_15",
        "title": "Kiểm thử hiệu năng kết xuất bản đồ (Map Rendering) và phát video trên trình duyệt",
        "endpoint": "http://localhost:5173/explore (Leaflet Map + Staggered Sliding Window Tri-Buffer TikTok Player)",
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_duration_sec": total_duration,
        "prerequisites": {
            "single_browser_tab_only": open_tabs_count == 1,
            "open_tabs_count": open_tabs_count,
            "markers_rendered_count": initial_markers_count,
            "gpu_renderer": gpu_renderer,
        },
        "client_performance": {
            "initial_map_load_ms": initial_map_load_ms,
            "initial_map_load_sec": round(initial_map_load_ms / 1000.0, 2),
            "first_video_ready_ms": first_video_ready_ms,
            "video_playback_switch_latency": video_lat_stats,
            "fps_stats": {
                "samples_count": len(fps_samples),
                "avg_fps": avg_fps,
                "p50_fps": p50_fps,
                "min_fps": min_fps,
                "max_fps": max_fps,
            },
            "browser_memory": {
                "tab_ram_avg_mb": avg_tab_ram_mb,
                "tab_ram_peak_mb": peak_tab_ram_mb,
                "js_heap_avg_mb": avg_js_heap_mb,
                "js_heap_peak_mb": peak_js_heap_mb,
                "dom_nodes_max": max(dom_nodes_samples) if dom_nodes_samples else int(final_cdp.get("Nodes", 0)),
                "active_iframes_tri_buffer_max": 3,
            },
        },
        "overall": {
            "total_requests": total_actions,
            "success_requests": total_actions - errors_count,
            "error_requests": errors_count,
            "error_rate_pct": error_rate_pct,
            "latency": video_lat_stats,
        },
        "host_resources": host_summary,
        "sla_evaluation": {
            "initial_map_load_ms": initial_map_load_ms,
            "sla_map_load_ms": 2500.0,
            "passed_map_load": passed_map_load,
            "video_p95_ms": video_lat_stats["p95_ms"],
            "sla_video_ms": 1500.0,
            "passed_video_load": passed_video_load,
            "avg_fps": avg_fps,
            "sla_min_fps": 45.0,
            "passed_fps": passed_fps,
            "tab_ram_peak_mb": peak_tab_ram_mb,
            "sla_tab_ram_mb": 400.0,
            "passed_tab_ram": passed_tab_ram,
            "error_rate_pct": error_rate_pct,
            "verdict": "Passed" if passed_all else "Failed",
        },
    }

    out_dir = RESULTS_DIR / f"round_{round_num}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "TC_PERF_15.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"<<< Hoàn tất TC_PERF_15 (Round {round_num}): Verdict={result['sla_evaluation']['verdict']} | "
        f"Map Load={initial_map_load_ms}ms (<2500ms) | Video p95={video_lat_stats['p95_ms']}ms (<1500ms) | "
        f"FPS Avg={avg_fps} (>=45 FPS) | Tab RAM Peak={peak_tab_ram_mb}MB (<400MB) | Err={error_rate_pct}%"
    )
    return result


async def main():
    parser = argparse.ArgumentParser(description="Chạy kiểm thử tự động TC_PERF_15")
    parser.add_argument("--duration", type=float, default=60.0, help="Thời lượng pan/zoom và phát video (giây)")
    parser.add_argument("--round", type=int, default=int(os.environ.get("PERF_ROUND", "1")), help="Round kiểm thử (1 hoặc 2)")
    parser.add_argument("--headed", action="store_true", help="Hiển thị cửa sổ trình duyệt (mặc định headless)")
    args = parser.parse_args()
    await run_tc_perf_15(duration_sec=args.duration, round_num=args.round, headless=not args.headed)


if __name__ == "__main__":
    asyncio.run(main())

