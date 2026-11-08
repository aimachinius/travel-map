import argparse
import asyncio
import datetime
import json
from pathlib import Path
import time

import httpx
import psycopg
import redis as sync_redis
from tornado.websocket import websocket_connect

from perf_engine import (
    AIServerSSHMonitor,
    DATA_DIR,
    HostResourceMonitor,
    LOGS_DIR,
    compute_latency_stats,
    ensure_backend_healthy,
    execute_standard_load_test,
    save_tc_result,
)

DB_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/foodspot_db"
REDIS_URL = "redis://127.0.0.1:6379/0"
AI_TUNNEL_EXTRACT_URL = "https://funk-smooth-alive-hosting.trycloudflare.com/api/v1/extract"

REAL_TIKTOK_URLS = [
    "https://www.tiktok.com/@mr.tn291/video/7599459386158779669",
    "https://www.tiktok.com/@namvivu112200/video/7667883156413943061",
    "https://www.tiktok.com/@chuyencuadanang_official/video/7621186492538490133",
    "https://www.tiktok.com/@leladanang/video/7685175735635463431",
    "https://www.tiktok.com/@kenhcuatienn/video/7665161172185910536",
    "https://www.tiktok.com/@anngaynoithat/video/7641148019907382535",
    "https://www.tiktok.com/@mustgo.vn/video/7619652695288204564",
    "https://www.tiktok.com/@leladanang/video/7659320777950383367",
]


def load_seeded_meta() -> dict:
    return json.loads((DATA_DIR / "seeded_ids.json").read_text(encoding="utf-8"))


async def run_tc_perf_08(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_08 — Kiểm thử tải tiếp nhận URL video vào hàng đợi xử lý (Analysis Queue)
    Endpoint thực tế: POST /api/v1/videos/submit [Mapped from POST /api/v1/videos/analyze]
    Kịch bản: Ramp-up 30s -> Duy trì 50 VUs, 20 req/giây (180s * scale) -> Ramp-down 30s
    SLA: HTTP 202 Accepted với p95 < 400 ms, Error Rate < 0.1%, 100% đẩy vào Redis Queue.
    """
    users_20 = meta["users_sample_20"]
    r_sync = sync_redis.from_url(REDIS_URL, decode_responses=True)
    r_sync.delete("queue:high_priority")

    async def submit_video_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        u = users_20[idx % len(users_20)]
        headers = {"Authorization": f"Bearer {u['access_token']}"}
        # Sử dụng URL hợp lệ riêng cho bài test Queue để luôn tạo analysis_run PENDING mới và đẩy vào Redis
        vid_num = 7550000000000000000 + idx
        payload = {
            "video_url": f"https://www.tiktok.com/@perf_queue_tc08/video/{vid_num}",
            "force_reanalyze": True,
        }
        t0 = time.perf_counter()
        try:
            resp = await client.post("/api/v1/videos/submit", json=payload, headers=headers)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            ok = resp.status_code == 202
            return (202 if ok else resp.status_code), lat_ms, None if ok else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    def cleanup_and_check_queue():
        q_len_after = r_sync.llen("queue:high_priority")
        # Dọn dẹp queue:high_priority và các bản ghi perf_queue_tc08 để không bắn ratusan URL giả sang Colab thật
        r_sync.delete("queue:high_priority")
        conn = psycopg.connect(DB_DSN)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM analysis_runs WHERE submitted_url LIKE '%@perf_queue_tc08/%';"
            )
            enqueued_db_count = cur.fetchone()[0]
            cur.execute(
                "DELETE FROM analysis_runs WHERE submitted_url LIKE '%@perf_queue_tc08/%';"
            )
            cur.execute(
                "DELETE FROM videos WHERE video_url LIKE '%@perf_queue_tc08/%';"
            )
            conn.commit()
        conn.close()
        return {
            "redis_queue_high_priority_len_before_cleanup": q_len_after,
            "total_enqueued_in_db": enqueued_db_count,
            "cleaned_up_synthetic_tasks": True,
        }

    try:
        return await execute_standard_load_test(
            tc_id="TC_PERF_08",
            title="Kiểm thử tải tiếp nhận URL video vào hàng đợi xử lý (Analysis Queue)",
            endpoint_desc="POST /api/v1/videos/submit (HTTP 202 Accepted -> Redis queue:high_priority)",
            request_fn=submit_video_req,
            vus=50,
            target_rps=20.0,
            ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
            steady_sec=max(20.0, round(180.0 * scale, 1)),
            ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
            sla_p95_ms=400.0,
            sla_error_rate_pct=0.1,
            extra_checks_fn=cleanup_and_check_queue,
        )
    finally:
        r_sync.close()


async def run_tc_perf_09(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_09 — Kiểm thử tải truy xuất video đã có kết quả phân tích (Completed Videos)
    Endpoint thực tế: GET /api/v1/videos/{video_id} & GET /api/v1/videos/analysis/{analysis_run_id}
    Kịch bản: Ramp-up 30s -> Duy trì 100 VUs, 45 req/giây (180s * scale) -> Ramp-down 30s
    SLA: p95 < 250 ms, Error Rate = 0%, CPU < 70%
    """
    primary_token = meta["primary_user"]["access_token"]
    headers = {"Authorization": f"Bearer {primary_token}"}
    all_run_ids = meta["completed_analysis_run_ids"]
    all_vid_ids = meta["completed_video_ids_for_primary_user"]
    run_ids = all_run_ids[:40]
    vid_ids = all_vid_ids[:40]

    async def get_completed_video_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        t0 = time.perf_counter()
        try:
            if idx % 2 == 0:
                rid = run_ids[idx % len(run_ids)]
                resp = await client.get(f"/api/v1/videos/analysis/{rid}", headers=headers)
            else:
                vid = vid_ids[idx % len(vid_ids)]
                resp = await client.get(f"/api/v1/videos/{vid}", headers=headers)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return resp.status_code, lat_ms, None if resp.status_code == 200 else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    return await execute_standard_load_test(
        tc_id="TC_PERF_09",
        title="Kiểm thử tải truy xuất video đã có kết quả phân tích (Completed Videos)",
        endpoint_desc="GET /api/v1/videos/analysis/{run_id} & GET /api/v1/videos/{video_id}",
        request_fn=get_completed_video_req,
        vus=100,
        target_rps=45.0,
        ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
        steady_sec=max(20.0, round(180.0 * scale, 1)),
        ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
        sla_p95_ms=250.0,
        sla_error_rate_pct=0.0,
        extra_checks_fn=lambda: {
            "completed_analysis_runs_pool": len(all_run_ids),
            "completed_videos_pool": len(all_vid_ids),
        },
    )


async def run_tc_perf_10(num_videos: int = 6) -> dict:
    """
    TC_PERF_10 — Kiểm thử tải xử lý AI Pipeline trên Google Colab Free (Tesla T4 GPU)
    Luồng xử lý: Gửi task qua Cloudflare Tunnel -> Colab Free (Tesla T4 15GB VRAM)
    chạy AI Pipeline -> Trả kết quả; Đồng thời giám sát qua SSH (nvidia-smi VRAM, System RAM).
    SLA:
      - Thời gian xử lý toàn trình p95 < 45 giây/video (45000 ms), Error Rate < 5%
      - Colab Free SLA: GPU VRAM < 13.5 GB / 15 GB (Zero CUDA OOM), System RAM Colab < 11 GB / 12.7 GB
    """
    tc_id = "TC_PERF_10"
    title = "Kiểm thử tải xử lý AI Pipeline trên Google Colab Free (Tesla T4 GPU)"
    print(f"\n>>> Đang chạy {tc_id}: {title} (Gửi {num_videos} video thực tế qua Cloudflare Tunnel + Giám sát SSH T4)...")

    host_monitor = HostResourceMonitor(interval_sec=2.0)
    ssh_monitor = AIServerSSHMonitor(log_filename="ssh_R2_TC_PERF_10.log", interval_sec=2.0)
    host_monitor.start()
    ssh_monitor.start()

    latencies_ms: list[float] = []
    video_results: list[dict] = []
    error_count = 0
    t_start = time.perf_counter()

    # Worker concurrency = 1 trên 1 GPU Tesla T4 để đo chính xác thời gian xử lý từng video qua Tunnel mà không bị xếp hàng chờ khóa GPU đơn
    sem = asyncio.Semaphore(1)

    async with httpx.AsyncClient(timeout=180.0) as client:
        async def process_one_video(v_idx: int, url: str):
            nonlocal error_count
            async with sem:
                v_t0 = time.perf_counter()
                try:
                    resp = await client.post(AI_TUNNEL_EXTRACT_URL, json={"url": url})
                    dur_ms = round((time.perf_counter() - v_t0) * 1000.0, 2)
                    latencies_ms.append(dur_ms)
                    body = resp.json() if resp.status_code == 200 else {"raw": resp.text[:300]}
                    is_ok = resp.status_code == 200 and (
                        body.get("success") is True or str(body.get("status", "")).upper() == "SUCCESS"
                    )
                    if not is_ok:
                        error_count += 1
                    rest_info = (body.get("data") or {}).get("restaurant") if isinstance(body, dict) else None
                    exec_metrics = (body.get("data") or {}).get("execution_metrics") if isinstance(body, dict) else None
                    video_results.append(
                        {
                            "index": v_idx + 1,
                            "url": url,
                            "http_status": resp.status_code,
                            "duration_ms": dur_ms,
                            "duration_sec": round(dur_ms / 1000.0, 2),
                            "success": is_ok,
                            "restaurant_extracted": rest_info,
                            "ai_execution_metrics": exec_metrics,
                        }
                    )
                    print(f"  [TC_PERF_10] Video #{v_idx + 1} hoàn tất trong {round(dur_ms / 1000.0, 2)}s | HTTP {resp.status_code} | OK={is_ok}")
                except Exception as e:
                    dur_ms = round((time.perf_counter() - v_t0) * 1000.0, 2)
                    latencies_ms.append(dur_ms)
                    error_count += 1
                    video_results.append(
                        {
                            "index": v_idx + 1,
                            "url": url,
                            "http_status": 0,
                            "duration_ms": dur_ms,
                            "duration_sec": round(dur_ms / 1000.0, 2),
                            "success": False,
                            "error": str(e),
                        }
                    )
                    print(f"  [TC_PERF_10] Video #{v_idx + 1} lỗi sau {round(dur_ms / 1000.0, 2)}s: {e}")

        selected_urls = [REAL_TIKTOK_URLS[i % len(REAL_TIKTOK_URLS)] for i in range(num_videos)]
        tasks = [asyncio.create_task(process_one_video(i, u)) for i, u in enumerate(selected_urls)]
        await asyncio.gather(*tasks)

    total_duration = round(time.perf_counter() - t_start, 2)
    host_summary = host_monitor.stop()
    ssh_summary = ssh_monitor.stop()

    lat_stats = compute_latency_stats(latencies_ms)
    err_rate_pct = round((error_count / max(1, num_videos)) * 100.0, 2)
    p95_sec = round(lat_stats["p95_ms"] / 1000.0, 2)

    vram_max_gb = ssh_summary.get("vram_max_used_gb", 0.0)
    sys_ram_max_gb = ssh_summary.get("sys_ram_max_used_gb", 0.0)
    passed_sla = (
        lat_stats["p95_ms"] <= 45000.0
        and err_rate_pct <= 5.0
        and vram_max_gb < 13.5
        and sys_ram_max_gb < 11.0
    )

    result = {
        "tc_id": tc_id,
        "title": title,
        "endpoint": AI_TUNNEL_EXTRACT_URL,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_duration_sec": total_duration,
        "overall": {
            "total_requests": num_videos,
            "success_requests": num_videos - error_count,
            "error_requests": error_count,
            "error_rate_pct": err_rate_pct,
            "throughput_videos_per_min": round((num_videos / max(0.001, total_duration)) * 60.0, 2),
            "latency": lat_stats,
            "p95_sec": p95_sec,
        },
        "colab_gpu_ssh_telemetry": ssh_summary,
        "host_resources": host_summary,
        "video_details": video_results,
        "sla_evaluation": {
            "steady_p95_ms": lat_stats["p95_ms"],
            "steady_p95_sec": p95_sec,
            "steady_error_rate_pct": err_rate_pct,
            "colab_vram_max_gb": vram_max_gb,
            "colab_sys_ram_max_gb": sys_ram_max_gb,
            "passed_client_sla": passed_sla,
            "verdict": "Passed" if passed_sla else "Failed",
        },
    }

    save_tc_result(tc_id, result)
    print(
        f"<<< Hoàn tất {tc_id}: Verdict={result['sla_evaluation']['verdict']} | "
        f"p95={p95_sec}s (SLA < 45s) | VRAM Max={vram_max_gb}GB | Colab RAM Max={sys_ram_max_gb}GB"
    )
    return result


async def run_tc_perf_11(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_11 — Kiểm thử độ trễ đẩy thông báo thời gian thực qua WebSocket
    Giao thức thực tế: WS ws://127.0.0.1:8000/api/v1/ws?token=<JWT_ACCESS_TOKEN>
    Kịch bản:
      - Mở đồng thời 150 kết nối WebSocket trên máy local
      - Phát 20 bản tin/giây trong (180s * scale) giây
    SLA:
      - Độ trễ truyền tin p95 < 150 ms, Error Rate (rớt kết nối) = 0%
      - Mức tiêu thụ RAM của 150 kết nối WebSocket < 300 MB
    """
    tc_id = "TC_PERF_11"
    title = "Kiểm thử độ trễ đẩy thông báo thời gian thực qua WebSocket"
    ensure_backend_healthy()
    duration_sec = max(20.0, round(180.0 * scale, 1))
    print(f"\n>>> Đang chạy {tc_id}: {title} (150 kết nối WS đồng thời, 20 msg/s trong {duration_sec}s)...")

    monitor = HostResourceMonitor(interval_sec=1.0)
    monitor.start()
    t0 = time.perf_counter()

    users_20 = meta["users_sample_20"]
    connections = []
    connect_latencies_ms = []
    dropped_connections = 0

    # 1. Mở đồng thời 150 kết nối WebSocket
    async def open_one_ws(conn_idx: int):
        nonlocal dropped_connections
        u = users_20[conn_idx % len(users_20)]
        ws_url = f"ws://127.0.0.1:8000/api/v1/ws?token={u['access_token']}"
        c_t0 = time.perf_counter()
        try:
            ws = await websocket_connect(ws_url, connect_timeout=15.0)
            c_lat = (time.perf_counter() - c_t0) * 1000.0
            connect_latencies_ms.append(c_lat)
            connections.append(ws)
        except Exception:
            dropped_connections += 1

    # Mở theo từng batch 30 kết nối để không nghẽn DB check user lúc bắt tay
    for b_start in range(0, 150, 30):
        batch_tasks = [open_one_ws(i) for i in range(b_start, min(150, b_start + 30))]
        await asyncio.gather(*batch_tasks)

    print(f"  [TC_PERF_11] Đã mở thành công {len(connections)}/150 kết nối WebSocket (Dropped={dropped_connections}).")

    # 2. Phát 20 bản tin sự kiện/giây trong duration_sec giây qua 150 kết nối WebSocket
    msg_latencies_ms: list[float] = []
    msg_errors = 0
    total_msgs = 0
    stop_time = time.perf_counter() + duration_sec

    async def send_recv_ping(ws_conn):
        nonlocal msg_errors, total_msgs
        m_t0 = time.perf_counter()
        total_msgs += 1
        try:
            await ws_conn.write_message("ping")
            reply = await asyncio.wait_for(ws_conn.read_message(), timeout=5.0)
            m_lat = (time.perf_counter() - m_t0) * 1000.0
            msg_latencies_ms.append(m_lat)
            if reply != "pong":
                msg_errors += 1
        except Exception:
            msg_errors += 1

    tick_idx = 0
    while time.perf_counter() < stop_time and connections:
        tick_start = time.perf_counter()
        # Phát 20 bản tin trong mỗi giây tới 20 kết nối xoay vòng trong tập 150 kết nối
        selected_conns = [connections[(tick_idx * 20 + k) % len(connections)] for k in range(20)]
        await asyncio.gather(*(send_recv_ping(c) for c in selected_conns))
        tick_idx += 1
        elapsed = time.perf_counter() - tick_start
        if elapsed < 1.0 and time.perf_counter() + (1.0 - elapsed) < stop_time:
            await asyncio.sleep(1.0 - elapsed)

    # 3. Đóng toàn bộ 150 kết nối
    for ws in connections:
        try:
            ws.close()
        except Exception:
            pass

    total_duration = round(time.perf_counter() - t0, 2)
    host_summary = monitor.stop()

    lat_stats = compute_latency_stats(msg_latencies_ms)
    conn_lat_stats = compute_latency_stats(connect_latencies_ms)
    err_rate_pct = round(((dropped_connections + msg_errors) / max(1, total_msgs + 150)) * 100.0, 3)
    ram_delta_mb = max(0.0, host_summary.get("ram_delta_mb", 0.0))

    passed_sla = (
        len(connections) == 150
        and dropped_connections == 0
        and err_rate_pct == 0.0
        and lat_stats["p95_ms"] <= 150.0
        and ram_delta_mb < 300.0
    )

    result = {
        "tc_id": tc_id,
        "title": title,
        "endpoint": "WS /api/v1/ws?token=<JWT_ACCESS_TOKEN> [Mapped from WS /ws/notifications]",
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_duration_sec": total_duration,
        "overall": {
            "concurrent_connections_target": 150,
            "concurrent_connections_established": len(connections),
            "dropped_connections": dropped_connections,
            "total_requests": total_msgs,
            "success_requests": total_msgs - msg_errors,
            "error_requests": msg_errors + dropped_connections,
            "error_rate_pct": err_rate_pct,
            "actual_rps": round(total_msgs / max(0.001, duration_sec), 2),
            "latency": lat_stats,
            "handshake_latency": conn_lat_stats,
        },
        "host_resources": host_summary,
        "sla_evaluation": {
            "steady_p95_ms": lat_stats["p95_ms"],
            "steady_error_rate_pct": err_rate_pct,
            "ws_ram_delta_mb": ram_delta_mb,
            "passed_client_sla": passed_sla,
            "verdict": "Passed" if passed_sla else "Failed",
        },
    }

    save_tc_result(tc_id, result)
    print(
        f"<<< Hoàn tất {tc_id}: Verdict={result['sla_evaluation']['verdict']} | "
        f"Conns={len(connections)}/150 | Msg p95={lat_stats['p95_ms']}ms | Err={err_rate_pct}% | RAM delta={ram_delta_mb}MB"
    )
    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=0.25, help="Tỷ lệ thời gian chạy")
    parser.add_argument("--ai-videos", type=int, default=6, help="Số lượng video chạy qua Colab AI ở TC_PERF_10")
    parser.add_argument("--tc", type=str, default="all", help="Chạy TC cụ thể hoặc all")
    args = parser.parse_args()

    meta = load_seeded_meta()
    if args.tc in ("all", "TC_PERF_08"):
        await run_tc_perf_08(meta, scale=args.scale)
    if args.tc in ("all", "TC_PERF_09"):
        await run_tc_perf_09(meta, scale=args.scale)
    if args.tc in ("all", "TC_PERF_10"):
        await run_tc_perf_10(num_videos=args.ai_videos)
    if args.tc in ("all", "TC_PERF_11"):
        await run_tc_perf_11(meta, scale=args.scale)


if __name__ == "__main__":
    asyncio.run(main())
