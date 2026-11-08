import datetime
import json
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = BASE_DIR / "results"
ROUND1_DIR = RESULTS_DIR / "round_1"
ROUND2_DIR = RESULTS_DIR / "round_2"
LOGS_DIR = BASE_DIR / "logs"
PERF_MD_PATH = BASE_DIR / "performance_testing.md"
BAO_CAO_MD_PATH = BASE_DIR / "bao cao.md"


def format_tc_round1_summary(tc_id: str, data: dict) -> str:
    verdict = data.get("sla_evaluation", {}).get("verdict", "Pending")
    overall = data.get("overall", {})
    lat = overall.get("latency", {})
    host = data.get("host_resources", {})
    sla_eval = data.get("sla_evaluation", {})
    extra = data.get("extra_checks", {})

    lines = [f"**{verdict}**"]

    if tc_id == "TC_PERF_04":
        stages = data.get("stages", {})
        sp = stages.get("spike", {})
        sp_ramp = stages.get("spike_ramp", {})
        sp_hold = stages.get("spike_hold", {})
        rec = stages.get("recovery", {})
        base = stages.get("baseline", {})
        lines.append(
            f"- **Baseline (15 VUs trong {base.get('duration_sec', 60)}s)**: Tổng `{base.get('total_requests', 0)}` reqs | "
            f"p50 = `{base.get('latency', {}).get('p50_ms', 0)} ms`, "
            f"p95 = `{base.get('latency', {}).get('p95_ms', 0)} ms`, Error Rate = `{base.get('error_rate_pct', 0)}%`"
        )
        if sp_ramp and sp_hold:
            lines.append(
                f"- **Spike Ramp-up (120 VUs / 50 RPS trong {sp_ramp.get('duration_sec', 15)}s)**: Tổng `{sp_ramp.get('total_requests', 0)}` reqs | "
                f"p50 = `{sp_ramp.get('latency', {}).get('p50_ms', 0)} ms`, p95 = `{sp_ramp.get('latency', {}).get('p95_ms', 0)} ms`, "
                f"Error Rate = `{sp_ramp.get('error_rate_pct', 0)}%`"
            )
            lines.append(
                f"- **Spike Hold (120 VUs / 50 RPS trong {sp_hold.get('duration_sec', 60)}s)**: Tổng `{sp_hold.get('total_requests', 0)}` reqs | "
                f"p50 = `{sp_hold.get('latency', {}).get('p50_ms', 0)} ms`, p95 = `{sp_hold.get('latency', {}).get('p95_ms', 0)} ms`, "
                f"Error Rate = `{sp_hold.get('error_rate_pct', 0)}%` (Tổng hợp Spike: `{sp.get('total_requests', 0)}` reqs, p95 = `{sp.get('latency', {}).get('p95_ms', 0)} ms`, Err = `{sp.get('error_rate_pct', 0)}%`)"
            )
        else:
            lines.append(
                f"- **Spike (120 VUs / 50 RPS)**: Tổng `{sp.get('total_requests', 0)}` reqs | "
                f"p50 = `{sp.get('latency', {}).get('p50_ms', 0)} ms`, p95 = `{sp.get('latency', {}).get('p95_ms', 0)} ms`, "
                f"Error Rate = `{sp.get('error_rate_pct', 0)}%`"
            )
        lines.append(
            f"- **Recovery (15 VUs trong {rec.get('duration_sec', 15)}s)**: Tổng `{rec.get('total_requests', 0)}` reqs | "
            f"p50 = `{rec.get('latency', {}).get('p50_ms', 0)} ms`, p95 = `{rec.get('latency', {}).get('p95_ms', 0)} ms`, "
            f"Error Rate = `{rec.get('error_rate_pct', 0)}%` | Worker Alive = `{extra.get('uvicorn_worker_alive_after_spike')}`"
        )
        lines.append(
            f"- **Laptop & Hạ tầng**: CPU Avg = `{host.get('cpu_avg_pct', 0)}%` (Peak `{host.get('cpu_max_pct', 0)}%`), "
            f"RAM Avg = `{host.get('ram_avg_pct', 0)}%` (Min Free `{host.get('ram_min_avail_mb', 0)} MB`, RAM Delta `{host.get('ram_delta_mb', 0)} MB`) | "
            f"Tỷ lệ request thực tế: `{extra.get('traffic_mix', '90% nearby / 10% login')}`"
        )
        prereqs = data.get("prerequisites", {})
        if prereqs:
            lines.append(
                f"- **Xác minh điều kiện tiên quyết**: `Uvicorn --backlog={prereqs.get('uvicorn_backlog_value')}` (Workers: `{prereqs.get('uvicorn_workers_count')}`), `PostgreSQL max_connections={prereqs.get('postgres_max_connections')}` -> **{'ĐẠT' if prereqs.get('prerequisites_met') else 'CHƯA ĐẠT'}**"
            )
    elif tc_id == "TC_PERF_10":
        colab = data.get("colab_gpu_ssh_telemetry", {})
        lines.append(
            f"- **Pipeline Latency**: p50 = `{round(lat.get('p50_ms', 0)/1000.0, 2)} s`, "
            f"p95 = `{sla_eval.get('steady_p95_sec', 0)} s` (`{lat.get('p95_ms', 0)} ms`), "
            f"Avg = `{round(lat.get('avg_ms', 0)/1000.0, 2)} s`, Error Rate = `{overall.get('error_rate_pct', 0)}%` "
            f"(`{overall.get('success_requests', 0)}/{overall.get('total_requests', 0)}` videos)"
        )
        lines.append(
            f"- **Colab Free T4 (SSH `nvidia-smi`)**: GPU = `{colab.get('gpu_name', 'Tesla T4')}`, "
            f"VRAM Peak = `{colab.get('vram_max_used_mb', 0)} MB` (`{colab.get('vram_max_used_gb', 0)} GB / 15 GB`), "
            f"GPU Util Peak = `{colab.get('gpu_util_max_pct', 0)}%`, Temp Peak = `{colab.get('gpu_temp_max_c', 0)}°C`, "
            f"Colab System RAM Peak = `{colab.get('sys_ram_max_used_gb', 0)} GB / 12.7 GB`"
        )
    elif tc_id == "TC_PERF_11":
        lines.append(
            f"- **WebSocket Connections**: `{overall.get('concurrent_connections_established', 0)}/150` kết nối đồng thời "
            f"(Dropped = `{overall.get('dropped_connections', 0)}`, Error Rate = `{overall.get('error_rate_pct', 0)}%`)"
        )
        lines.append(
            f"- **Độ trễ truyền tin (Ping/Event)**: p50 = `{lat.get('p50_ms', 0)} ms`, "
            f"p95 = `{lat.get('p95_ms', 0)} ms`, p99 = `{lat.get('p99_ms', 0)} ms`, RPS = `{overall.get('actual_rps', 0)} msg/s`"
        )
        lines.append(
            f"- **Hạ tầng Laptop**: WS RAM Delta = `{sla_eval.get('ws_ram_delta_mb', 0)} MB`, "
            f"CPU Avg = `{host.get('cpu_avg_pct', 0)}%`, RAM Avg = `{host.get('ram_avg_pct', 0)}%`"
        )
    elif tc_id == "TC_PERF_15":
        cp = data.get("client_performance", {})
        v_lat = cp.get("video_playback_switch_latency", lat)
        fps = cp.get("fps_stats", {})
        mem = cp.get("browser_memory", {})
        prereq = data.get("prerequisites", {})
        lines.append(
            f"- **Tải bản đồ & Phát video**: Tải bản đồ lần đầu = `{cp.get('initial_map_load_ms', 0)} ms` (`{cp.get('initial_map_load_sec', 0)} s`, SLO `< 2.5 s`, `{prereq.get('markers_rendered_count', 50)}` markers) | "
            f"Phát/chuyển video (`{overall.get('total_requests', 0)}` lượt): p50 = `{v_lat.get('p50_ms', 0)} ms`, p95 = `{v_lat.get('p95_ms', 0)} ms` (SLO `< 1,500 ms`), Max = `{v_lat.get('max_ms', 0)} ms`, Error Rate = `{overall.get('error_rate_pct', 0)}%`"
        )
        lines.append(
            f"- **Tốc độ khung hình (Pan/Zoom FPS) & Bộ nhớ Tab (Chrome CDP)**: FPS Avg = `{fps.get('avg_fps', 0)} FPS` (p50 = `{fps.get('p50_fps', 0)} FPS`, Min = `{fps.get('min_fps', 0)} FPS`, Max = `{fps.get('max_fps', 0)} FPS`, SLO `>= 45 FPS`) | "
            f"Tab Renderer RAM Peak = `{mem.get('tab_ram_peak_mb', 0)} MB` (Avg = `{mem.get('tab_ram_avg_mb', 0)} MB`, SLO `< 400 MB`), JS Heap Peak = `{mem.get('js_heap_peak_mb', 0)} MB` (Tri-Buffer max `{mem.get('active_iframes_tri_buffer_max', 3)}` iframes)"
        )
        lines.append(
            f"- **Laptop & GPU tích hợp**: GPU = `{prereq.get('gpu_renderer', 'Intel UHD/Iris Xe')}`, Single Tab = `{prereq.get('single_browser_tab_only', True)}` | "
            f"CPU Avg = `{host.get('cpu_avg_pct', 0)}%` (Peak `{host.get('cpu_max_pct', 0)}%`), RAM Avg = `{host.get('ram_avg_pct', 0)}%` (Min Free `{host.get('ram_min_avail_mb', 0)} MB`)"
        )
    elif tc_id == "TC_PERF_16":
        bp = data.get("breaking_point_analysis", {})
        stages = data.get("stages", {})
        step_strs = []
        for k, v in stages.items():
            if k.startswith("step_"):
                step_strs.append(
                    f"`{v['vus']} VUs`: p95=`{v['latency']['p95_ms']}ms`, Err=`{v['error_rate_pct']}%`, RAM=`{v.get('ram_percent_at_end')}%`"
                )
        lines.append("- **Kết quả từng bậc tải**: " + " | ".join(step_strs))
        lines.append(
            f"- **Ngưỡng giới hạn (Breaking Point)**: `{bp.get('breaking_point_vus')}` ({bp.get('breaking_reason')})"
        )
        lines.append(
            f"- **Khả năng tự hồi phục (Recovery)**: p95 = `{bp.get('recovery_p95_ms')} ms`, "
            f"Services Alive = `{bp.get('services_survived_without_crash')}`"
        )
    elif tc_id == "TC_PERF_17":
        bp = data.get("backpressure_verification", {})
        colab = data.get("colab_gpu_ssh_telemetry", {})
        lines.append(
            f"- **Tiếp nhận 30 videos (HTTP 202)**: `{overall.get('accepted_202_requests', 0)}/30` thành công | "
            f"p50 = `{lat.get('p50_ms', 0)} ms`, p95 = `{lat.get('p95_ms', 0)} ms`, Max = `{lat.get('max_ms', 0)} ms`, "
            f"Error Rate = `{overall.get('error_rate_pct', 0)}%`"
        )
        lines.append(
            f"- **Backpressure & Hàng đợi Redis**: Peak Queue Depth = `{bp.get('peak_redis_queue_depth', 0)}` tasks | "
            f"Worker Concurrency thực tế (`status=PROCESSING`) = `{bp.get('max_concurrent_processing_in_worker', 1)}` task"
        )
        lines.append(
            f"- **Colab Free T4 (SSH `nvidia-smi`)**: VRAM Peak = `{colab.get('vram_max_used_mb', 0)} MB` "
            f"(`{colab.get('vram_max_used_gb', 0)} GB / 15 GB`, Zero CUDA OOM), Colab RAM Peak = `{colab.get('sys_ram_max_used_gb', 0)} GB`"
        )
    elif tc_id == "TC_PERF_18":
        fb = data.get("failover_breakdown", {})
        m_lat = fb.get("map_latency", {})
        s_lat = fb.get("video_submit_latency", {})
        lines.append(
            f"- **Luồng Bản đồ (`GET /api/v1/places/nearby-videos`) khi đứt Tunnel**: "
            f"`{fb.get('map_requests_count', 0)}` reqs | p50 = `{m_lat.get('p50_ms', 0)} ms`, "
            f"p95 = `{m_lat.get('p95_ms', 0)} ms`, Error Rate = `{fb.get('map_error_rate_pct', 0)}%`"
        )
        lines.append(
            f"- **Luồng Gửi Video (`POST /api/v1/videos/submit`) khi đứt Tunnel**: "
            f"`{fb.get('video_submit_requests_count', 0)}` reqs | HTTP 202 p95 = `{s_lat.get('p95_ms', 0)} ms`, "
            f"Error Rate tiếp nhận = `{fb.get('video_submit_error_rate_pct', 0)}%`"
        )
        lines.append(f"- **Phát hiện thực tế tại Worker**: {fb.get('architectural_finding', '')}")
    else:
        st_steady = data.get("stages", {}).get("steady", overall)
        s_lat = st_steady.get("latency", lat)
        lines.append(
            f"- **Client Metrics (Steady-state)**: Tổng `{overall.get('total_requests', 0)}` reqs "
            f"(Steady `{st_steady.get('total_requests', 0)}` reqs, `{st_steady.get('actual_rps', 0)} req/s`) | "
            f"p50 = `{s_lat.get('p50_ms', 0)} ms`, p95 = `{s_lat.get('p95_ms', 0)} ms`, "
            f"p99 = `{s_lat.get('p99_ms', 0)} ms`, Avg = `{s_lat.get('avg_ms', 0)} ms`, "
            f"Error Rate = `{st_steady.get('error_rate_pct', 0)}%`"
        )
        lines.append(
            f"- **Laptop & Hạ tầng**: CPU Avg = `{host.get('cpu_avg_pct', 0)}%` (Peak `{host.get('cpu_max_pct', 0)}%`), "
            f"RAM Avg = `{host.get('ram_avg_pct', 0)}%` (Min Free `{host.get('ram_min_avail_mb', 0)} MB`, "
            f"RAM Delta `{host.get('ram_delta_mb', 0)} MB`)"
        )
        if extra:
            extra_kv = ", ".join(f"`{k}={v}`" for k, v in extra.items() if not isinstance(v, (dict, list)))
            if extra_kv:
                lines.append(f"- **Thông số DB/Cache/Hạ tầng bổ sung**: {extra_kv}")

    return "\n".join(lines)


def update_performance_testing_md():
    content = PERF_MD_PATH.read_text(encoding="utf-8")

    passed_cnt = 0
    failed_cnt = 0
    pending_cnt = 0
    na_cnt = 0

    tc_ids = [
        "TC_PERF_01",
        "TC_PERF_04",
        "TC_PERF_05",
        "TC_PERF_06",
        "TC_PERF_07",
        "TC_PERF_08",
        "TC_PERF_09",
        "TC_PERF_10",
        "TC_PERF_11",
        "TC_PERF_12",
        "TC_PERF_13",
        "TC_PERF_14",
        "TC_PERF_15",
        "TC_PERF_16",
        "TC_PERF_17",
        "TC_PERF_18",
    ]

    for tc_id in tc_ids:
        json_file = ROUND1_DIR / f"{tc_id}.json"
        if not json_file.exists():
            pending_cnt += 1
            continue

        data = json.loads(json_file.read_text(encoding="utf-8"))
        verdict = data.get("sla_evaluation", {}).get("verdict", "Pending")
        if verdict == "Passed":
            passed_cnt += 1
        elif verdict == "Failed":
            failed_cnt += 1
        else:
            pending_cnt += 1

        summary_block = format_tc_round1_summary(tc_id, data)

        # Thay thế phần **Round 1:** của tc_id
        pattern = re.compile(
            rf"(#### {tc_id} — .*?\*\*Round 1:\*\*\s*\n\s*\n)(.*?)(\n\s*\n\*\*Round 2:\*\*)",
            re.DOTALL,
        )
        content = pattern.sub(rf"\g<1>{summary_block}\g<3>", content, count=1)

    # Cập nhật bảng thống kê Round 1
    stats_pattern = re.compile(r"\| Round 1 \| \d+ \| \d+ \| \d+ \| \d+ \|")
    content = stats_pattern.sub(
        f"| Round 1 | {passed_cnt} | {failed_cnt} | {pending_cnt} | {na_cnt} |",
        content,
        count=1,
    )

    # Cập nhật phần Round 2 nếu có dữ liệu trong ROUND2_DIR
    r2_passed = 0
    r2_failed = 0
    r2_pending = 0
    r2_na = 0

    for tc_id in tc_ids:
        json_file_r2 = ROUND2_DIR / f"{tc_id}.json"
        if not json_file_r2.exists():
            r2_pending += 1
            continue

        data_r2 = json.loads(json_file_r2.read_text(encoding="utf-8"))
        verdict_r2 = data_r2.get("sla_evaluation", {}).get("verdict", "Pending")
        if verdict_r2 == "Passed":
            r2_passed += 1
        elif verdict_r2 == "Failed":
            r2_failed += 1
        else:
            r2_pending += 1

        summary_block_r2 = format_tc_round1_summary(tc_id, data_r2)

        pattern_r2 = re.compile(
            rf"(#### {tc_id} — .*?\*\*Round 2:\*\*\s*\n\s*\n)(.*?)(\n\s*\n\*\*Round 3:\*\*)",
            re.DOTALL,
        )
        content = pattern_r2.sub(rf"\g<1>{summary_block_r2}\g<3>", content, count=1)

    stats_pattern_r2 = re.compile(r"\| Round 2 \| \d+ \| \d+ \| \d+ \| \d+ \|")
    content = stats_pattern_r2.sub(
        f"| Round 2 | {r2_passed} | {r2_failed} | {r2_pending} | {r2_na} |",
        content,
        count=1,
    )

    PERF_MD_PATH.write_text(content, encoding="utf-8")
    print(
        f"Đã cập nhật {PERF_MD_PATH}: "
        f"R1(Passed={passed_cnt}, Failed={failed_cnt}, Pending={pending_cnt}) | "
        f"R2(Passed={r2_passed}, Failed={r2_failed}, Pending={r2_pending})"
    )


def format_tc_table_cell(tc_id: str, data: dict) -> str:
    """Định dạng ngắn gọn trên 1 dòng (dùng <br><br>) cho bảng trong bao cao.md."""
    raw = format_tc_round1_summary(tc_id, data)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    # Bỏ dòng đầu tiên (**Passed** / **Failed**) vì đã có cột Round 2 riêng
    bullet_lines = []
    for ln in lines[1:]:
        if ln.startswith("- "):
            ln = "• " + ln[2:]
        ln = ln.replace("|", "\\|")
        bullet_lines.append(ln)
    return "<br><br>".join(bullet_lines)


def update_bao_cao_md():
    if not BAO_CAO_MD_PATH.exists():
        return
    lines = BAO_CAO_MD_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    has_r2_detail_col = "**Kết quả Round 2**" in (lines[0] if lines else "")

    for idx, line in enumerate(lines):
        if not line.strip().startswith("|"):
            new_lines.append(line)
            continue
        # Tách các cột của bảng Markdown (xử lý \| bên trong nội dung)
        placeholder = "__ESCAPED_PIPE__"
        safe_line = line.replace("\\|", placeholder)
        parts = [p.strip().replace(placeholder, "\\|") for p in safe_line.split("|")[1:-1]]
        if not parts:
            new_lines.append(line)
            continue

        first_col = parts[0]
        if idx == 0 and not has_r2_detail_col:
            # Chèn cột **Kết quả Round 2** ngay trước cột **Round 2** (index 10)
            parts.insert(10, "**Kết quả Round 2**")
        elif idx == 1 and not has_r2_detail_col:
            parts.insert(10, ":---")
        elif first_col.startswith("**NHÓM"):
            if not has_r2_detail_col:
                parts.insert(10, "")
        elif first_col.startswith("**TC_PERF_"):
            tc_id = first_col.replace("*", "").strip()
            if not has_r2_detail_col:
                parts.insert(10, "Pending")
            # Sau khi chèn, vị trí các cột Round 2 là:
            # 10: Kết quả Round 2, 11: Round 2, 12: Test Date (R2), 13: Tester (R2)
            if tc_id == "TC_PERF_15":
                json_r1 = ROUND1_DIR / f"{tc_id}.json"
                if json_r1.exists():
                    d1 = json.loads(json_r1.read_text(encoding="utf-8"))
                    verdict_r1 = d1.get("sla_evaluation", {}).get("verdict", "Pending")
                    parts[6] = format_tc_table_cell(tc_id, d1)
                    parts[7] = verdict_r1
                    parts[8] = "08-Thg11"
                    parts[9] = "Lợi"

            json_r2 = ROUND2_DIR / f"{tc_id}.json"
            if json_r2.exists():
                d2 = json.loads(json_r2.read_text(encoding="utf-8"))
                verdict_r2 = d2.get("sla_evaluation", {}).get("verdict", "Pending")
                parts[10] = format_tc_table_cell(tc_id, d2)
                parts[11] = verdict_r2
                parts[12] = "08-Thg11"
                parts[13] = "Lợi"
            elif tc_id == "TC_PERF_15":
                parts[10] = "Pending"
                parts[11] = "Pending"
                parts[12] = "08-Thg11"
                parts[13] = "Lợi"

        new_lines.append("| " + " | ".join(parts) + " |")

    BAO_CAO_MD_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Đã cập nhật {BAO_CAO_MD_PATH} với kết quả Round 2.")


if __name__ == "__main__":
    update_performance_testing_md()
    update_bao_cao_md()

