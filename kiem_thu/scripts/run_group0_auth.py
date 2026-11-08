import argparse
import asyncio
import csv
import datetime
import json
from pathlib import Path
import random
import time

import httpx

from perf_engine import (
    DATA_DIR,
    HostResourceMonitor,
    compute_latency_stats,
    ensure_backend_healthy,
    execute_standard_load_test,
    run_load_stage,
    save_tc_result,
)


def load_users_200() -> list[dict[str, str]]:
    csv_path = DATA_DIR / "users_200.csv"
    users = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row)
    return users


async def run_tc_perf_01(users: list[dict[str, str]], scale: float = 1.0) -> dict:
    """
    TC_PERF_01 — Kiểm thử tải đăng nhập và cấp phát JWT Token
    Endpoint: POST /api/v1/auth/login
    Kịch bản: Ramp-up 30s -> Duy trì 30 VUs, 15 RPS (180s * scale) -> Ramp-down 30s
    SLA: p95 < 500 ms, Error Rate < 0.5%
    """

    async def login_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        u = users[idx % len(users)]
        payload = {"username_or_email": u["email"], "password": u["password"]}
        t0 = time.perf_counter()
        try:
            resp = await client.post("/api/v1/auth/login", json=payload)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return resp.status_code, lat_ms, None if resp.status_code == 200 else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    return await execute_standard_load_test(
        tc_id="TC_PERF_01",
        title="Kiểm thử tải đăng nhập và cấp phát JWT Token",
        endpoint_desc="POST /api/v1/auth/login",
        request_fn=login_req,
        vus=30,
        target_rps=15.0,
        ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
        steady_sec=max(15.0, round(180.0 * scale, 1)),
        ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
        sla_p95_ms=500.0,
        sla_error_rate_pct=0.5,
        extra_checks_fn=lambda: {
            "password_hash_algorithm": "Argon2 (pwdlib.PasswordHash.recommended)",
            "users_csv_count": len(users),
        },
    )


def check_tc_perf_04_prerequisites() -> dict:
    prereq = {
        "uvicorn_backlog_configured": False,
        "uvicorn_backlog_value": None,
        "uvicorn_workers_count": 1,
        "postgres_max_connections": None,
        "prerequisites_met": False,
    }
    # 1. Kiểm tra PostgreSQL max_connections
    try:
        import psycopg
        with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/foodspot_db") as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW max_connections;")
                row = cur.fetchone()
                if row:
                    prereq["postgres_max_connections"] = int(row[0])
    except Exception as e:
        prereq["postgres_error"] = str(e)

    # 2. Kiểm tra cờ --backlog 512 và số worker của Uvicorn trong Docker container
    try:
        import subprocess
        res = subprocess.run(["docker", "top", "foodspot-backend"], capture_output=True, text=True, check=False)
        output = res.stdout
        if "--backlog 512" in output:
            prereq["uvicorn_backlog_configured"] = True
            prereq["uvicorn_backlog_value"] = 512
        elif "--backlog" in output:
            prereq["uvicorn_backlog_configured"] = True
        if "--workers 2" in output:
            prereq["uvicorn_workers_count"] = 2
    except Exception as e:
        prereq["docker_error"] = str(e)

    prereq["prerequisites_met"] = (
        prereq["postgres_max_connections"] == 100
        and prereq["uvicorn_backlog_configured"] is True
    )
    return prereq


async def run_tc_perf_04(users: list[dict[str, str]], scale: float = 1.0) -> dict:
    """
    TC_PERF_04 — Kiểm thử tăng tải đột biến (Spike) khi người dùng truy cập đồng loạt
    Endpoint: GET /api/v1/places/nearby (90%) + POST /api/v1/auth/login (10%)
      (Thực tế Backend triển khai GET /api/v1/places/nearby-videos)
    Kịch bản tải:
      - Nền (Baseline): 15 VUs trong 1 phút (60s * scale)
      - Tăng vọt (Spike Ramp-up): 120 VUs (50 req/giây) trong 15 giây (15s * scale)
      - Duy trì (Spike Hold): 120 VUs (50 req/giây) trong 1 phút (60s * scale)
      - Hạ tải (Recovery): 15 VUs trong 15 giây (15s * scale)
    SLA: Spike p95 < 1500 ms, Error Rate < 1%; Recovery p95 < 500 ms.
    """
    ensure_backend_healthy()
    tc_id = "TC_PERF_04"
    title = "Kiểm thử tăng tải đột biến (Spike) khi người dùng truy cập đồng loạt"
    print(f"\n>>> Đang chạy {tc_id}: {title} (scale={scale})...")

    # Kiểm tra điều kiện tiên quyết theo đặc tả
    prereqs = check_tc_perf_04_prerequisites()
    print(
        f"  [Prerequisite Check] PostgreSQL max_connections={prereqs['postgres_max_connections']} "
        f"(Yêu cầu: 100) -> {'ĐẠT' if prereqs['postgres_max_connections'] == 100 else 'KHÔNG ĐẠT'}"
    )
    print(
        f"  [Prerequisite Check] Uvicorn --backlog={prereqs['uvicorn_backlog_value']} "
        f"(Yêu cầu: 512) -> {'ĐẠT' if prereqs['uvicorn_backlog_configured'] else 'KHÔNG ĐẠT'}, "
        f"workers={prereqs['uvicorn_workers_count']}"
    )

    monitor = HostResourceMonitor(interval_sec=1.0)
    monitor.start()
    t0 = time.perf_counter()

    # Tọa độ tâm Đà Nẵng đã nằm trong lưới discovery_scans
    coords = [
        (16.0610, 108.2208),
        (16.0544, 108.2022),
        (16.0712, 108.2235),
        (16.0471, 108.2198),
    ]

    nearby_count = 0
    login_count = 0

    async def mixed_spike_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        nonlocal nearby_count, login_count
        # 90% GET /api/v1/places/nearby-videos, 10% POST /api/v1/auth/login
        is_nearby = (idx % 10) < 9
        req_t0 = time.perf_counter()
        try:
            if is_nearby:
                nearby_count += 1
                lat, lon = coords[idx % len(coords)]
                resp = await client.get(
                    "/api/v1/places/nearby-videos",
                    params={"lat": lat, "lon": lon, "radius_m": 2000.0, "limit": 20},
                )
            else:
                login_count += 1
                u = users[idx % len(users)]
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"username_or_email": u["email"], "password": u["password"]},
                )
            lat_ms = (time.perf_counter() - req_t0) * 1000.0
            return resp.status_code, lat_ms, None if resp.status_code == 200 else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - req_t0) * 1000.0
            return 0, lat_ms, str(e)

    limits = httpx.Limits(max_connections=250, max_keepalive_connections=150)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", limits=limits, timeout=10.0) as client:
        # Pha 1: Nền 15 VUs trong 1 phút (60s)
        s_baseline = await run_load_stage(
            client,
            mixed_spike_req,
            vus=15,
            target_rps=10.0,
            duration_sec=max(5.0, round(60.0 * scale, 1)),
            stage_name="baseline_15vus_60s",
        )
        # Pha 2: Tăng vọt (Spike) lên 120 VUs (50 req/giây) trong 15 giây
        s_spike_ramp = await run_load_stage(
            client,
            mixed_spike_req,
            vus=120,
            target_rps=50.0,
            duration_sec=max(5.0, round(15.0 * scale, 1)),
            stage_name="spike_ramp_120vus_15s",
        )
        # Pha 3: Duy trì 120 VUs (50 req/giây) trong 1 phút (60s)
        s_spike_hold = await run_load_stage(
            client,
            mixed_spike_req,
            vus=120,
            target_rps=50.0,
            duration_sec=max(5.0, round(60.0 * scale, 1)),
            stage_name="spike_hold_120vus_60s",
        )
        # Pha 4: Hạ về 15 VUs trong 15 giây
        s_recovery = await run_load_stage(
            client,
            mixed_spike_req,
            vus=15,
            target_rps=10.0,
            duration_sec=max(5.0, round(15.0 * scale, 1)),
            stage_name="recovery_15vus_15s",
        )

        # Kiểm tra healthcheck sau Spike xem Uvicorn worker còn sống không
        worker_alive = False
        for _ in range(3):
            try:
                health_resp = await client.get("/health", timeout=10.0)
                if health_resp.status_code == 200:
                    worker_alive = True
                    break
            except Exception:
                await asyncio.sleep(2.0)

    total_duration = round(time.perf_counter() - t0, 2)
    host_summary = monitor.stop()
    ensure_backend_healthy()

    spike_lats = s_spike_ramp["_raw_latencies"] + s_spike_hold["_raw_latencies"]
    all_lats = (
        s_baseline["_raw_latencies"]
        + spike_lats
        + s_recovery["_raw_latencies"]
    )
    for st in (s_baseline, s_spike_ramp, s_spike_hold, s_recovery):
        st.pop("_raw_latencies", None)

    spike_total_reqs = s_spike_ramp["total_requests"] + s_spike_hold["total_requests"]
    spike_err_reqs = s_spike_ramp["error_requests"] + s_spike_hold["error_requests"]
    spike_dur = round(s_spike_ramp["duration_sec"] + s_spike_hold["duration_sec"], 2)
    spike_err_rate = round((spike_err_reqs / spike_total_reqs) * 100.0, 3) if spike_total_reqs > 0 else 0.0
    spike_combined_stats = compute_latency_stats(spike_lats)

    s_spike_combined = {
        "stage": "spike_combined_120vus_75s",
        "vus": 120,
        "target_rps": 50.0,
        "duration_sec": spike_dur,
        "total_requests": spike_total_reqs,
        "success_requests": spike_total_reqs - spike_err_reqs,
        "error_requests": spike_err_reqs,
        "error_rate_pct": spike_err_rate,
        "actual_rps": round(spike_total_reqs / max(0.001, spike_dur), 2),
        "latency": spike_combined_stats,
    }

    total_reqs = sum(st["total_requests"] for st in (s_baseline, s_spike_ramp, s_spike_hold, s_recovery))
    total_errs = sum(st["error_requests"] for st in (s_baseline, s_spike_ramp, s_spike_hold, s_recovery))
    overall_err_rate = round((total_errs / total_reqs) * 100.0, 3) if total_reqs > 0 else 0.0

    spike_p95 = s_spike_combined["latency"]["p95_ms"]
    spike_err = s_spike_combined["error_rate_pct"]
    recovery_p95 = s_recovery["latency"]["p95_ms"]

    passed_sla = (
        spike_p95 <= 1500.0
        and spike_err <= 1.0
        and recovery_p95 <= 500.0
        and worker_alive
    )

    result = {
        "tc_id": tc_id,
        "title": title,
        "endpoint": "GET /api/v1/places/nearby-videos (90%) + POST /api/v1/auth/login (10%) [Mapped from /places/nearby]",
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_duration_sec": total_duration,
        "overall": {
            "total_requests": total_reqs,
            "success_requests": total_reqs - total_errs,
            "error_requests": total_errs,
            "error_rate_pct": overall_err_rate,
            "actual_rps": round(total_reqs / max(0.001, total_duration), 2),
            "nearby_requests": nearby_count,
            "login_requests": login_count,
            "nearby_ratio_pct": round((nearby_count / max(1, total_reqs)) * 100.0, 2),
            "login_ratio_pct": round((login_count / max(1, total_reqs)) * 100.0, 2),
            "latency": compute_latency_stats(all_lats),
        },
        "stages": {
            "baseline": s_baseline,
            "spike_ramp": s_spike_ramp,
            "spike_hold": s_spike_hold,
            "spike": s_spike_combined,
            "recovery": s_recovery,
        },
        "host_resources": host_summary,
        "prerequisites": prereqs,
        "extra_checks": {
            "uvicorn_worker_alive_after_spike": worker_alive,
            "prerequisites_met": prereqs["prerequisites_met"],
            "postgres_max_connections": prereqs["postgres_max_connections"],
            "uvicorn_backlog": prereqs["uvicorn_backlog_value"],
            "uvicorn_workers": prereqs["uvicorn_workers_count"],
            "traffic_mix": f"nearby={nearby_count} ({round((nearby_count / max(1, total_reqs)) * 100.0, 1)}%), login={login_count} ({round((login_count / max(1, total_reqs)) * 100.0, 1)}%)",
        },
        "sla_evaluation": {
            "spike_p95_ms": spike_p95,
            "spike_error_rate_pct": spike_err,
            "recovery_p95_ms": recovery_p95,
            "passed_client_sla": passed_sla,
            "verdict": "Passed" if passed_sla else "Failed",
        },
    }

    save_tc_result(tc_id, result)
    print(
        f"<<< Hoàn tất {tc_id}: Verdict={result['sla_evaluation']['verdict']} | "
        f"Spike p95={spike_p95}ms | Recovery p95={recovery_p95}ms | Err={spike_err}%"
    )
    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=0.25, help="Tỷ lệ thời gian chạy (1.0 = full, 0.25 = nhanh)")
    parser.add_argument("--tc", type=str, default="all", help="Chạy TC cụ thể hoặc all")
    args = parser.parse_args()

    users = load_users_200()
    if args.tc in ("all", "TC_PERF_01"):
        await run_tc_perf_01(users, scale=args.scale)
    if args.tc in ("all", "TC_PERF_04"):
        await run_tc_perf_04(users, scale=args.scale)


if __name__ == "__main__":
    asyncio.run(main())
