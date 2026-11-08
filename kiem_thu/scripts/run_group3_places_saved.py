import argparse
import asyncio
import datetime
import json
from pathlib import Path
import time

import httpx
import psycopg

from perf_engine import (
    DATA_DIR,
    execute_standard_load_test,
)

DB_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/foodspot_db"


def load_seeded_meta() -> dict:
    return json.loads((DATA_DIR / "seeded_ids.json").read_text(encoding="utf-8"))


def check_join_explain(place_id: str, user_id: str) -> dict:
    conn = psycopg.connect(DB_DSN)
    with conn.cursor() as cur:
        cur.execute(
            """
            EXPLAIN (ANALYZE, FORMAT JSON)
            SELECT v.id, vpm.confidence_status, vpm.matched_at
            FROM videos v
            JOIN video_place_matches vpm ON vpm.video_id = v.id
            WHERE vpm.place_id = %s
            ORDER BY CASE WHEN vpm.confidence_status = 'HIGH' THEN 1
                          WHEN vpm.confidence_status = 'MEDIUM' THEN 2
                          ELSE 3 END ASC,
                     v.created_at DESC
            LIMIT 50 OFFSET 0;
            """,
            (place_id,),
        )
        p1 = cur.fetchone()[0][0]

        cur.execute(
            """
            EXPLAIN (ANALYZE, FORMAT JSON)
            SELECT sp.id, p.id, p.name
            FROM saved_places sp
            JOIN places p ON p.id = sp.place_id
            WHERE sp.user_id = %s AND p.is_active = true
            ORDER BY sp.created_at DESC
            LIMIT 20 OFFSET 0;
            """,
            (user_id,),
        )
        p2 = cur.fetchone()[0][0]

        cur.execute("SELECT deadlocks FROM pg_stat_database WHERE datname = 'foodspot_db';")
        deadlocks = cur.fetchone()[0]
    conn.close()
    return {
        "place_videos_join_exec_ms": round(float(p1.get("Execution Time", 0.0)), 3),
        "saved_places_join_exec_ms": round(float(p2.get("Execution Time", 0.0)), 3),
        "saved_places_uses_index": "Index" in json.dumps(p2.get("Plan", {})),
        "db_deadlocks_count": deadlocks,
    }


async def run_tc_perf_12(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_12 — Kiểm thử tải xem chi tiết quán và danh sách video review liên quan
    Endpoint thực tế: GET /api/v1/places/{place_id} & GET /api/v1/places/{place_id}/videos
    Kịch bản: Ramp-up 30s -> Duy trì 80 VUs, 35 req/giây (180s * scale) -> Ramp-down 30s
    SLA: p95 < 500 ms, Error Rate < 0.1%, PostgreSQL JOIN < 50 ms
    """
    rich_places = meta["places_with_20plus_videos"]
    primary_uid = meta["primary_user"]["user_id"]

    async def place_detail_videos_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        pid = rich_places[idx % len(rich_places)]
        t0 = time.perf_counter()
        try:
            if idx % 2 == 0:
                resp = await client.get(f"/api/v1/places/{pid}/videos", params={"limit": 20, "offset": 0})
            else:
                resp = await client.get(f"/api/v1/places/{pid}")
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return resp.status_code, lat_ms, None if resp.status_code == 200 else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    return await execute_standard_load_test(
        tc_id="TC_PERF_12",
        title="Kiểm thử tải xem chi tiết quán và danh sách video review liên quan",
        endpoint_desc="GET /api/v1/places/{place_id}/videos & GET /api/v1/places/{place_id} [Mapped from detail-with-videos]",
        request_fn=place_detail_videos_req,
        vus=80,
        target_rps=35.0,
        ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
        steady_sec=max(20.0, round(180.0 * scale, 1)),
        ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
        sla_p95_ms=500.0,
        sla_error_rate_pct=0.1,
        extra_checks_fn=lambda: check_join_explain(rich_places[0], primary_uid),
    )


async def run_tc_perf_13(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_13 — Kiểm thử tải thao tác lưu và bỏ lưu địa điểm/video yêu thích
    Endpoint thực tế: POST & DELETE /api/v1/saved/places/{place_id} & /api/v1/saved/videos/{video_id}
    Kịch bản: Ramp-up 30s -> Duy trì 50 VUs, 20 req/giây (180s * scale) -> Ramp-down 30s
    SLA: p95 < 350 ms, Error Rate < 0.1%, Zero Deadlock
    """
    users_20 = meta["users_sample_20"]
    places_pool = meta["sample_place_ids"][120:200]
    videos_pool = meta["sample_video_ids"][120:200]
    deadlocks_before = check_join_explain(meta["places_with_20plus_videos"][0], users_20[0]["user_id"])["db_deadlocks_count"]

    async def save_unsave_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        u = users_20[idx % len(users_20)]
        headers = {"Authorization": f"Bearer {u['access_token']}"}
        pid = places_pool[idx % len(places_pool)]
        vid = videos_pool[idx % len(videos_pool)]

        t0 = time.perf_counter()
        try:
            # Đảm bảo tính nhất quán khi bắn đồng thời:
            # POST là Idempotent (201 hoặc 200); hoặc thực hiện POST trước rồi DELETE
            mode = idx % 3
            if mode == 0:
                resp = await client.post(f"/api/v1/saved/places/{pid}", headers=headers)
                ok = resp.status_code in (200, 201)
            elif mode == 1:
                resp = await client.post(f"/api/v1/saved/videos/{vid}", headers=headers)
                ok = resp.status_code in (200, 201)
            else:
                # Đảm bảo đã lưu trước khi xóa để đo đúng thao tác DELETE hợp lệ (204)
                await client.post(f"/api/v1/saved/places/{pid}", headers=headers)
                t0 = time.perf_counter()
                resp = await client.delete(f"/api/v1/saved/places/{pid}", headers=headers)
                ok = resp.status_code in (200, 204, 404)
                if resp.status_code == 404:
                    # Nếu VU khác vừa xóa mili-giây trước trong điều kiện race, gọi lại POST idempotent
                    resp = await client.post(f"/api/v1/saved/places/{pid}", headers=headers)
                    ok = resp.status_code in (200, 201)

            lat_ms = (time.perf_counter() - t0) * 1000.0
            return (200 if ok else resp.status_code), lat_ms, None if ok else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    def deadlock_check():
        after = check_join_explain(meta["places_with_20plus_videos"][0], users_20[0]["user_id"])
        return {
            "deadlocks_before": deadlocks_before,
            "deadlocks_after": after["db_deadlocks_count"],
            "new_deadlocks": after["db_deadlocks_count"] - deadlocks_before,
        }

    return await execute_standard_load_test(
        tc_id="TC_PERF_13",
        title="Kiểm thử tải thao tác lưu và bỏ lưu địa điểm/video yêu thích",
        endpoint_desc="POST & DELETE /api/v1/saved/places/{place_id} & /api/v1/saved/videos/{video_id}",
        request_fn=save_unsave_req,
        vus=50,
        target_rps=20.0,
        ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
        steady_sec=max(20.0, round(180.0 * scale, 1)),
        ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
        sla_p95_ms=350.0,
        sla_error_rate_pct=0.1,
        extra_checks_fn=deadlock_check,
    )


async def run_tc_perf_14(meta: dict, scale: float = 1.0) -> dict:
    """
    TC_PERF_14 — Kiểm thử tải truy xuất, phân trang và lọc danh sách đã lưu
    Endpoint thực tế: GET /api/v1/saved/places?limit=20&offset=0 & GET /api/v1/saved/videos?limit=20&offset=0
    Kịch bản: Ramp-up 30s -> Duy trì 60 VUs, 25 req/giây (180s * scale) -> Ramp-down 30s
    SLA: p95 < 600 ms, Error Rate < 0.1%, Sử dụng đúng Composite/User Index
    """
    users_20 = meta["users_sample_20"]

    async def list_saved_req(client: httpx.AsyncClient, idx: int) -> tuple[int, float, str | None]:
        u = users_20[idx % len(users_20)]
        headers = {"Authorization": f"Bearer {u['access_token']}"}
        offset = (idx % 4) * 20
        t0 = time.perf_counter()
        try:
            if idx % 2 == 0:
                resp = await client.get("/api/v1/saved/places", params={"limit": 20, "offset": offset}, headers=headers)
            else:
                resp = await client.get("/api/v1/saved/videos", params={"limit": 20, "offset": offset}, headers=headers)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return resp.status_code, lat_ms, None if resp.status_code == 200 else resp.text[:120]
        except Exception as e:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return 0, lat_ms, str(e)

    return await execute_standard_load_test(
        tc_id="TC_PERF_14",
        title="Kiểm thử tải truy xuất, phân trang và lọc danh sách đã lưu",
        endpoint_desc="GET /api/v1/saved/places?limit=20&offset={0..60} & GET /api/v1/saved/videos",
        request_fn=list_saved_req,
        vus=60,
        target_rps=25.0,
        ramp_up_sec=max(5.0, round(30.0 * scale, 1)),
        steady_sec=max(20.0, round(180.0 * scale, 1)),
        ramp_down_sec=max(5.0, round(30.0 * scale, 1)),
        sla_p95_ms=600.0,
        sla_error_rate_pct=0.1,
        extra_checks_fn=lambda: check_join_explain(meta["places_with_20plus_videos"][0], users_20[0]["user_id"]),
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=float, default=0.25, help="Tỷ lệ thời gian chạy")
    parser.add_argument("--tc", type=str, default="all", help="Chạy TC cụ thể hoặc all")
    args = parser.parse_args()

    meta = load_seeded_meta()
    if args.tc in ("all", "TC_PERF_12"):
        await run_tc_perf_12(meta, scale=args.scale)
    if args.tc in ("all", "TC_PERF_13"):
        await run_tc_perf_13(meta, scale=args.scale)
    if args.tc in ("all", "TC_PERF_14"):
        await run_tc_perf_14(meta, scale=args.scale)


if __name__ == "__main__":
    asyncio.run(main())

