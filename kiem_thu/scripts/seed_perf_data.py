import csv
import datetime
import json
from pathlib import Path
import random
import time
import uuid

import jwt
import psycopg
from pwdlib import PasswordHash

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DB_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/foodspot_db"
JWT_SECRET_KEY = "foodspot_dev_secret_key_change_in_production_2026"
JWT_ALGORITHM = "HS256"
DEFAULT_PASSWORD = "Password123!"

# Tọa độ trung tâm Đà Nẵng (Cầu Rồng / Hải Châu / Sơn Trà / Thanh Khê / Ngũ Hành Sơn / Liên Chiểu)
DANANG_CENTER_LAT = 16.0610
DANANG_CENTER_LON = 108.2208

CATEGORIES = ["Quán ăn", "Quán cafe", "Ăn vặt", "Nhà hàng", "Hải sản", "Bún & Mì"]
STREETS = [
    "Nguyễn Văn Linh",
    "Bạch Đằng",
    "Trần Phú",
    "Lê Duẩn",
    "Điện Biên Phủ",
    "Võ Nguyên Giáp",
    "Ngô Quyền",
    "Hoàng Diệu",
    "Phan Châu Trinh",
    "Hùng Vương",
    "Nguyễn Tất Thành",
    "Hàm Nghi",
    "2 Tháng 9",
    "Núi Thành",
    "Trưng Nữ Vương",
]
DISTRICTS = [
    "Quận Hải Châu, Thành phố Đà Nẵng",
    "Quận Sơn Trà, Thành phố Đà Nẵng",
    "Quận Thanh Khê, Thành phố Đà Nẵng",
    "Quận Ngũ Hành Sơn, Thành phố Đà Nẵng",
    "Quận Liên Chiểu, Thành phố Đà Nẵng",
    "Quận Cẩm Lệ, Thành phố Đà Nẵng",
]


def create_jwt(user_id: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    return jwt.encode({"sub": user_id, "exp": expire}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def main():
    t0 = time.time()
    print("=== Bắt đầu Seed dữ liệu kiểm thử hiệu năng (Performance Test Seeding) ===")
    password_hasher = PasswordHash.recommended()
    shared_hash = password_hasher.hash(DEFAULT_PASSWORD)

    conn = psycopg.connect(DB_DSN)
    with conn.cursor() as cur:
        # 1. Seed 500 Users
        cur.execute("SELECT id, username, email FROM users WHERE username LIKE 'perf_user_%' ORDER BY username;")
        existing_perf_users = cur.fetchall()
        existing_usernames = {r[1] for r in existing_perf_users}

        new_users = []
        for i in range(1, 501):
            uname = f"perf_user_{i:04d}"
            email = f"perf_user_{i:04d}@foodspot.test"
            if uname not in existing_usernames:
                uid = uuid.uuid4()
                new_users.append((uid, uname, email, shared_hash, f"Perf Tester {i}", True))

        if new_users:
            print(f"Đang chèn thêm {len(new_users)} users để đạt mốc >= 500 users...")
            cur.executemany(
                """
                INSERT INTO users (id, username, email, password_hash, full_name, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING;
                """,
                new_users,
            )
            conn.commit()

        cur.execute("SELECT id, username, email FROM users WHERE username LIKE 'perf_user_%' ORDER BY username LIMIT 500;")
        perf_users = cur.fetchall()
        print(f"Tổng số perf_users sẵn sàng: {len(perf_users)}")

        # Xuất file users_200.csv
        csv_path = DATA_DIR / "users_200.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "username", "email", "password", "access_token"])
            for uid, uname, email in perf_users[:200]:
                writer.writerow([str(uid), uname, email, DEFAULT_PASSWORD, create_jwt(str(uid))])
        print(f"Đã xuất 200 users ra {csv_path}")

        # 2. Seed >= 500 Videos & COMPLETED analysis_runs
        cur.execute("SELECT count(*) FROM videos;")
        total_videos = cur.fetchone()[0]
        if total_videos < 600:
            need_v = 600 - total_videos
            print(f"Đang seed thêm {need_v} videos...")
            v_rows = []
            for i in range(need_v):
                vid = uuid.uuid4()
                p_vid = f"perf_vid_{i + 100000}"
                v_url = f"https://www.tiktok.com/@foodspot_tester/video/{7300000000000000000 + i}"
                v_rows.append(
                    (
                        vid,
                        "tiktok",
                        p_vid,
                        v_url,
                        f"Review ẩm thực Đà Nẵng #{i}",
                        "Quán ngon Đà Nẵng",
                        "Review chi tiết món ngon Đà Nẵng",
                        22.5,
                        4.2,
                    )
                )
            cur.executemany(
                """
                INSERT INTO videos (id, platform, platform_video_id, video_url, title, caption, transcript_text, duration_seconds, file_size_mb)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (platform, platform_video_id) DO NOTHING;
                """,
                v_rows,
            )
            conn.commit()

        cur.execute("SELECT id, video_url FROM videos LIMIT 600;")
        all_videos = cur.fetchall()

        # Đảm bảo có ít nhất 500 COMPLETED analysis_runs gắn với user đầu tiên & SYSTEM_DISCOVERY
        cur.execute("SELECT count(*) FROM analysis_runs WHERE status = 'COMPLETED';")
        completed_runs_count = cur.fetchone()[0]
        primary_user_id = perf_users[0][0]
        if completed_runs_count < 520:
            need_runs = 520 - completed_runs_count
            print(f"Đang seed thêm {need_runs} COMPLETED analysis_runs...")
            run_rows = []
            for i in range(need_runs):
                v_id, v_url = all_videos[i % len(all_videos)]
                run_rows.append(
                    (
                        uuid.uuid4(),
                        primary_user_id,
                        v_id,
                        v_url,
                        "COMPLETED",
                        "USER_SUBMIT",
                        1,
                        json.dumps({"frames_extracted": 6}),
                        json.dumps({"ocr_lines": ["Quán ăn Đà Nẵng"]}),
                        json.dumps({"total_sec": 12.4}),
                    )
                )
            cur.executemany(
                """
                INSERT INTO analysis_runs (id, user_id, video_id, submitted_url, status, trigger_source, priority, keyframes_data, ocr_data, execution_metrics)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::json, %s::json, %s::json);
                """,
                run_rows,
            )
            conn.commit()

        # 3. Seed đủ 10.000 Places tại Đà Nẵng (PostGIS POINT(lon lat))
        cur.execute("SELECT count(*) FROM places WHERE location IS NOT NULL;")
        places_count = cur.fetchone()[0]
        if places_count < 10000:
            need_p = 10000 - places_count
            print(f"Đang seed thêm {need_p} địa điểm (places) tại Đà Nẵng kèm tọa độ PostGIS...")
            random.seed(42)
            batch = []
            for i in range(need_p):
                pid = uuid.uuid4()
                # Phân bố quanh tâm Đà Nẵng (bán kính ~ 12km)
                lat = round(DANANG_CENTER_LAT + random.uniform(-0.06, 0.06), 6)
                lon = round(DANANG_CENTER_LON + random.uniform(-0.06, 0.06), 6)
                street = STREETS[i % len(STREETS)]
                dist = DISTRICTS[i % len(DISTRICTS)]
                cat = CATEGORIES[i % len(CATEGORIES)]
                house_no = (i % 450) + 1
                name = f"{cat} Đà Nẵng Perf #{i + 1}"
                addr = f"{house_no} Đường {street}, {dist}"
                batch.append((pid, name, addr, addr, lon, lat, lat, lon, cat, True))

                if len(batch) >= 2000:
                    cur.executemany(
                        """
                        INSERT INTO places (id, name, address, normalized_address, location, latitude, longitude, category, is_active)
                        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s);
                        """,
                        batch,
                    )
                    conn.commit()
                    batch.clear()
            if batch:
                cur.executemany(
                    """
                    INSERT INTO places (id, name, address, normalized_address, location, latitude, longitude, category, is_active)
                    VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s);
                    """,
                    batch,
                )
                conn.commit()

        # 4. Liên kết video_place_matches:
        # - Đảm bảo ít nhất 20 địa điểm có >= 25 videos liên kết (phục vụ TC_PERF_12)
        # - Đảm bảo có ít nhất 2.000 liên kết video_place_matches phân bố tại Đà Nẵng (phục vụ TC_PERF_06, 07, 16)
        cur.execute("SELECT id FROM places WHERE location IS NOT NULL LIMIT 2500;")
        sample_places = [r[0] for r in cur.fetchall()]
        video_ids = [r[0] for r in all_videos]

        cur.execute("SELECT count(*) FROM video_place_matches;")
        matches_count = cur.fetchone()[0]
        rich_place_ids = sample_places[:20]

        print("Đang đảm bảo dữ liệu liên kết video_place_matches (20 quán có >= 25 videos & 2000 quán trên bản đồ)...")
        match_rows = []
        conf_levels = ["HIGH", "MEDIUM", "LOW"]
        # 20 quán đầu tiên: mỗi quán 25 videos
        for p_idx, pid in enumerate(rich_place_ids):
            for v_idx in range(25):
                vid = video_ids[(p_idx * 25 + v_idx) % len(video_ids)]
                conf = conf_levels[v_idx % 3]
                match_rows.append((uuid.uuid4(), vid, pid, conf, 0.9, json.dumps(["audio", "vision"])))

        # 2000 quán tiếp theo: mỗi quán ít nhất 1 video
        if matches_count < 2000:
            for idx, pid in enumerate(sample_places[20:2020]):
                vid = video_ids[idx % len(video_ids)]
                conf = conf_levels[idx % 3]
                match_rows.append((uuid.uuid4(), vid, pid, conf, 0.85, json.dumps(["vision"])))

        if match_rows:
            cur.executemany(
                """
                INSERT INTO video_place_matches (id, video_id, place_id, confidence_status, confidence, evidence_sources)
                VALUES (%s, %s, %s, %s, %s, %s::json)
                ON CONFLICT (video_id, place_id) DO NOTHING;
                """,
                match_rows,
            )
            conn.commit()

        # 5. Seed >= 120 saved_places & >= 120 saved_videos cho 60 tài khoản test đầu tiên (phục vụ TC_PERF_14)
        print("Đang seed dữ liệu saved_places & saved_videos (>= 100 bản ghi/user cho nhóm test)...")
        saved_p_rows = []
        saved_v_rows = []
        # Cho 20 users đầu tiên mỗi user 110 saved_places và 110 saved_videos
        for u_idx in range(20):
            uid = perf_users[u_idx][0]
            cur.execute("SELECT count(*) FROM saved_places WHERE user_id = %s;", (uid,))
            cnt_sp = cur.fetchone()[0]
            if cnt_sp < 105:
                for p_i in range(110):
                    saved_p_rows.append((uuid.uuid4(), uid, sample_places[p_i]))

            cur.execute("SELECT count(*) FROM saved_videos WHERE user_id = %s;", (uid,))
            cnt_sv = cur.fetchone()[0]
            if cnt_sv < 105:
                for v_i in range(110):
                    saved_v_rows.append((uuid.uuid4(), uid, video_ids[v_i]))

        if saved_p_rows:
            cur.executemany(
                """
                INSERT INTO saved_places (id, user_id, place_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, place_id) DO NOTHING;
                """,
                saved_p_rows,
            )
        if saved_v_rows:
            cur.executemany(
                """
                INSERT INTO saved_videos (id, user_id, video_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, video_id) DO NOTHING;
                """,
                saved_v_rows,
            )
        conn.commit()

        # 6. Seed lưới discovery_scans phủ vùng Đà Nẵng trong 24h qua
        # Để khi chạy Load Test GET /api/v1/places/nearby-videos không kích hoạt Playwright Chromium cào TikTok ngoài ý muốn
        print("Đang cập nhật lưới discovery_scans tại Đà Nẵng (chống kích hoạt Playwright cào ngầm khi bắn tải PostGIS)...")
        scan_rows = []
        lat_steps = [16.00 + i * 0.008 for i in range(16)]
        lon_steps = [108.16 + j * 0.008 for j in range(16)]
        for lat_s in lat_steps:
            for lon_s in lon_steps:
                scan_rows.append(
                    (
                        uuid.uuid4(),
                        lon_s,
                        lat_s,
                        5000.0,
                        json.dumps(["quán ăn ở Đà Nẵng", "quán cafe ở Đà Nẵng"]),
                        25,
                    )
                )
        cur.execute("DELETE FROM discovery_scans WHERE radius_m = 5000.0;")
        cur.executemany(
            """
            INSERT INTO discovery_scans (id, center_location, radius_m, keywords_generated, videos_found_count, scanned_at)
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s::json, %s, NOW());
            """,
            scan_rows,
        )
        conn.commit()

        # Chạy ANALYZE để PostgreSQL cập nhật thống kê cho GIST Index và B-Tree Index
        cur.execute("ANALYZE;")
        conn.commit()

        # Thu thập danh sách ID để lưu vào seeded_ids.json
        cur.execute(
            """
            SELECT p.id, count(vpm.video_id) as vc
            FROM places p
            JOIN video_place_matches vpm ON vpm.place_id = p.id
            GROUP BY p.id
            HAVING count(vpm.video_id) >= 20
            LIMIT 20;
            """
        )
        places_with_20_videos = [str(r[0]) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT ar.id, ar.video_id
            FROM analysis_runs ar
            WHERE ar.user_id = %s AND ar.status = 'COMPLETED' AND ar.video_id IS NOT NULL
            LIMIT 500;
            """,
            (primary_user_id,),
        )
        completed_pairs = cur.fetchall()

        # Đếm tổng kết
        summary_counts = {}
        for t in ["users", "places", "videos", "video_place_matches", "analysis_runs", "saved_places", "saved_videos", "discovery_scans"]:
            cur.execute(f"SELECT count(*) FROM {t};")
            summary_counts[t] = cur.fetchone()[0]

    conn.close()

    seeded_meta = {
        "seeded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "table_counts": summary_counts,
        "primary_user": {
            "user_id": str(perf_users[0][0]),
            "username": perf_users[0][1],
            "email": perf_users[0][2],
            "password": DEFAULT_PASSWORD,
            "access_token": create_jwt(str(perf_users[0][0])),
        },
        "users_sample_20": [
            {
                "user_id": str(u[0]),
                "username": u[1],
                "email": u[2],
                "password": DEFAULT_PASSWORD,
                "access_token": create_jwt(str(u[0])),
            }
            for u in perf_users[:20]
        ],
        "places_with_20plus_videos": places_with_20_videos,
        "sample_place_ids": [str(p) for p in sample_places[:200]],
        "sample_video_ids": [str(v) for v in video_ids[:500]],
        "completed_analysis_run_ids": [str(r[0]) for r in completed_pairs[:500]],
        "completed_video_ids_for_primary_user": list({str(r[1]) for r in completed_pairs if r[1]}),
    }

    meta_path = DATA_DIR / "seeded_ids.json"
    meta_path.write_text(json.dumps(seeded_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Hoàn tất seed dữ liệu trong {round(time.time() - t0, 2)}s! Thống kê bảng: {summary_counts}")


if __name__ == "__main__":
    main()

