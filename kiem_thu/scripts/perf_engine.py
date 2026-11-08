import asyncio
import datetime
import json
import math
from pathlib import Path
import statistics
import subprocess
import threading
import time
from typing import Any, Callable, Coroutine

import httpx
import paramiko
import psutil
import psycopg
import redis

import os

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
ROUND1_DIR = RESULTS_DIR / "round_1"
ROUND2_DIR = RESULTS_DIR / "round_2"
LOGS_DIR = BASE_DIR / "logs"
PERF_ROUND = int(os.environ.get("PERF_ROUND", "2"))

for d in [DATA_DIR, RESULTS_DIR, ROUND1_DIR, ROUND2_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SSH_HOST = "2.tcp.us-cal-1.ngrok.io"
SSH_PORT = 10083
SSH_USER = "nippon"
SSH_PASS = "nippon"


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


def compute_latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {
            "count": 0,
            "min_ms": 0.0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }
    s = sorted(latencies_ms)
    return {
        "count": len(s),
        "min_ms": round(s[0], 2),
        "avg_ms": round(statistics.mean(s), 2),
        "p50_ms": percentile(s, 50),
        "p90_ms": percentile(s, 90),
        "p95_ms": percentile(s, 95),
        "p99_ms": percentile(s, 99),
        "max_ms": round(s[-1], 2),
    }


class HostResourceMonitor:
    """Giám sát CPU, RAM của Laptop và Redis trong suốt thời gian chạy Test Case."""

    def __init__(self, interval_sec: float = 1.0):
        self.interval_sec = interval_sec
        self.samples: list[dict[str, Any]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        return self.summarize()

    def _run(self):
        psutil.cpu_percent(interval=None)
        while not self._stop_event.is_set():
            vm = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            sample = {
                "ts": time.time(),
                "cpu_pct": cpu,
                "ram_pct": vm.percent,
                "ram_avail_mb": round(vm.available / (1024 * 1024), 2),
                "ram_used_mb": round(vm.used / (1024 * 1024), 2),
            }
            self.samples.append(sample)
            self._stop_event.wait(self.interval_sec)

    def summarize(self) -> dict[str, Any]:
        if not self.samples:
            vm = psutil.virtual_memory()
            return {
                "samples_count": 0,
                "cpu_avg_pct": psutil.cpu_percent(interval=0.2),
                "cpu_max_pct": 0.0,
                "ram_avg_pct": vm.percent,
                "ram_max_pct": vm.percent,
                "ram_min_avail_mb": round(vm.available / (1024 * 1024), 2),
                "ram_delta_mb": 0.0,
            }
        cpus = [s["cpu_pct"] for s in self.samples]
        rams = [s["ram_pct"] for s in self.samples]
        avails = [s["ram_avail_mb"] for s in self.samples]
        useds = [s["ram_used_mb"] for s in self.samples]
        return {
            "samples_count": len(self.samples),
            "cpu_avg_pct": round(statistics.mean(cpus), 2),
            "cpu_max_pct": round(max(cpus), 2),
            "ram_avg_pct": round(statistics.mean(rams), 2),
            "ram_max_pct": round(max(rams), 2),
            "ram_min_avail_mb": round(min(avails), 2),
            "ram_start_used_mb": useds[0],
            "ram_end_used_mb": useds[-1],
            "ram_delta_mb": round(useds[-1] - useds[0], 2),
        }


class AIServerSSHMonitor:
    """Giám sát GPU Tesla T4 (VRAM, Util, Temp) & System RAM trên Colab qua SSH và lưu log."""

    def __init__(self, log_filename: str, interval_sec: float = 3.0):
        self.log_path = LOGS_DIR / log_filename
        self.interval_sec = interval_sec
        self.samples: list[dict[str, Any]] = []
        self.raw_logs: list[str] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10.0)
        self.log_path.write_text("\n".join(self.raw_logs), encoding="utf-8")
        return self.summarize()

    def _run(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
            self.raw_logs.append(f"[{datetime.datetime.now().isoformat()}] Connected to AI Server {SSH_HOST}:{SSH_PORT}")
            cmd = (
                "LD_LIBRARY_PATH=/usr/lib64-nvidia:/usr/local/nvidia/lib64 "
                "/opt/bin/nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,memory.used,memory.total "
                "--format=csv,noheader,nounits && free -m | awk '/Mem:/ {print $2,$3,$7}' && "
                "ps aux | grep 'run_server.py' | grep -v grep | wc -l"
            )
            while not self._stop_event.is_set():
                try:
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
                    out = stdout.read().decode("utf-8", errors="replace").strip()
                    ts_iso = datetime.datetime.now().isoformat()
                    self.raw_logs.append(f"--- [{ts_iso}] ---\n{out}")
                    lines = [line.strip() for line in out.splitlines() if line.strip()]
                    if len(lines) >= 2:
                        gpu_parts = [p.strip() for p in lines[0].split(",")]
                        mem_parts = lines[1].split()
                        proc_cnt = int(lines[2]) if len(lines) >= 3 and lines[2].isdigit() else 1
                        if len(gpu_parts) >= 6 and len(mem_parts) >= 3:
                            self.samples.append(
                                {
                                    "ts": ts_iso,
                                    "gpu_name": gpu_parts[1],
                                    "gpu_temp_c": float(gpu_parts[2]),
                                    "gpu_util_pct": float(gpu_parts[3]),
                                    "vram_used_mb": float(gpu_parts[4]),
                                    "vram_total_mb": float(gpu_parts[5]),
                                    "sys_ram_total_mb": float(mem_parts[0]),
                                    "sys_ram_used_mb": float(mem_parts[1]),
                                    "sys_ram_avail_mb": float(mem_parts[2]),
                                    "worker_processes": proc_cnt,
                                }
                            )
                except Exception as loop_err:
                    self.raw_logs.append(f"[{datetime.datetime.now().isoformat()}] Sample error: {loop_err}")
                self._stop_event.wait(self.interval_sec)
        except Exception as e:
            self.raw_logs.append(f"[{datetime.datetime.now().isoformat()}] SSH connect error: {e}")
        finally:
            try:
                ssh.close()
            except Exception:
                pass

    def summarize(self) -> dict[str, Any]:
        if not self.samples:
            return {"samples_count": 0, "log_file": str(self.log_path)}
        vram_used = [s["vram_used_mb"] for s in self.samples]
        gpu_util = [s["gpu_util_pct"] for s in self.samples]
        gpu_temp = [s["gpu_temp_c"] for s in self.samples]
        sys_ram_used = [s["sys_ram_used_mb"] for s in self.samples]
        return {
            "samples_count": len(self.samples),
            "gpu_name": self.samples[0]["gpu_name"],
            "vram_total_mb": self.samples[0]["vram_total_mb"],
            "vram_max_used_mb": round(max(vram_used), 2),
            "vram_avg_used_mb": round(statistics.mean(vram_used), 2),
            "vram_max_used_gb": round(max(vram_used) / 1024.0, 2),
            "gpu_util_max_pct": round(max(gpu_util), 2),
            "gpu_util_avg_pct": round(statistics.mean(gpu_util), 2),
            "gpu_temp_max_c": round(max(gpu_temp), 2),
            "sys_ram_total_mb": self.samples[0]["sys_ram_total_mb"],
            "sys_ram_max_used_mb": round(max(sys_ram_used), 2),
            "sys_ram_max_used_gb": round(max(sys_ram_used) / 1024.0, 2),
            "worker_processes": max(s["worker_processes"] for s in self.samples),
            "log_file": str(self.log_path),
        }


async def run_load_stage(
    client: httpx.AsyncClient,
    request_fn: Callable[[httpx.AsyncClient, int], Coroutine[Any, Any, tuple[int, float, str | None]]],
    vus: int,
    target_rps: float,
    duration_sec: float,
    stage_name: str = "steady",
) -> dict[str, Any]:
    """
    Chạy 1 pha tải với số lượng VUs và target_rps chỉ định trong duration_sec giây.
    request_fn(client, req_idx) -> trả về (status_code, latency_ms, error_msg)
    """
    latencies: list[float] = []
    status_counts: dict[str, int] = {}
    errors: list[str] = []
    total_reqs = 0
    error_reqs = 0
    req_counter = 0

    stop_time = time.perf_counter() + duration_sec
    # Khoảng nghỉ trung bình trên mỗi VU để đạt target_rps: interval = vus / target_rps
    per_vu_interval = (vus / target_rps) if target_rps > 0 else 0.1

    async def vu_worker(vu_id: int):
        nonlocal total_reqs, error_reqs, req_counter
        # Stagger khởi động VU nhẹ để tránh đồng bộ hóa nhân tạo
        await asyncio.sleep((vu_id % max(1, vus)) * min(0.05, per_vu_interval / max(1, vus)))
        while time.perf_counter() < stop_time:
            iter_start = time.perf_counter()
            req_counter += 1
            curr_idx = req_counter
            status_code, lat_ms, err = await request_fn(client, curr_idx)
            total_reqs += 1
            latencies.append(lat_ms)
            st_key = str(status_code)
            status_counts[st_key] = status_counts.get(st_key, 0) + 1
            if err is not None or status_code >= 400 or status_code == 0:
                error_reqs += 1
                if err and len(errors) < 20:
                    errors.append(err)
            elapsed = time.perf_counter() - iter_start
            sleep_for = max(0.0, per_vu_interval - elapsed)
            if sleep_for > 0 and time.perf_counter() + sleep_for < stop_time:
                await asyncio.sleep(sleep_for)

    t_start = time.perf_counter()
    workers = [asyncio.create_task(vu_worker(i)) for i in range(max(1, vus))]
    await asyncio.gather(*workers, return_exceptions=True)
    actual_duration = max(0.001, time.perf_counter() - t_start)

    stats = compute_latency_stats(latencies)
    error_rate_pct = round((error_reqs / total_reqs) * 100.0, 3) if total_reqs > 0 else 0.0
    actual_rps = round(total_reqs / actual_duration, 2)

    return {
        "stage": stage_name,
        "vus": vus,
        "target_rps": target_rps,
        "duration_sec": round(actual_duration, 2),
        "total_requests": total_reqs,
        "success_requests": total_reqs - error_reqs,
        "error_requests": error_reqs,
        "error_rate_pct": error_rate_pct,
        "actual_rps": actual_rps,
        "latency": stats,
        "status_counts": status_counts,
        "sample_errors": errors[:10],
        "_raw_latencies": latencies,
    }


def ensure_backend_healthy():
    """Đảm bảo container foodspot-backend phản hồi /health trước khi bắt đầu Test Case mới."""
    try:
        r = httpx.get("http://127.0.0.1:8000/health", timeout=3.0)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    print("  [Recovery] foodspot-backend đang bị treo/quá tải pool, đang khởi động lại container để làm sạch trạng thái...")
    subprocess.run(["docker", "restart", "foodspot-backend"], check=False, capture_output=True)
    for _ in range(15):
        time.sleep(1.0)
        try:
            r = httpx.get("http://127.0.0.1:8000/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
    return False


async def execute_standard_load_test(
    tc_id: str,
    title: str,
    endpoint_desc: str,
    request_fn: Callable[[httpx.AsyncClient, int], Coroutine[Any, Any, tuple[int, float, str | None]]],
    vus: int,
    target_rps: float,
    ramp_up_sec: float,
    steady_sec: float,
    ramp_down_sec: float,
    sla_p95_ms: float,
    sla_error_rate_pct: float,
    extra_checks_fn: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ensure_backend_healthy()
    print(f"\n>>> Đang chạy {tc_id}: {title} (VUs={vus}, Target RPS={target_rps}, Steady={steady_sec}s)...")
    monitor = HostResourceMonitor(interval_sec=1.0)
    monitor.start()
    t0 = time.perf_counter()

    limits = httpx.Limits(max_connections=max(200, vus * 2), max_keepalive_connections=max(100, vus))
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", limits=limits, timeout=10.0) as client:
        # 1. Ramp-up (50% VUs & 50% RPS)
        s_ramp_up = await run_load_stage(
            client,
            request_fn,
            vus=max(1, vus // 2),
            target_rps=max(1.0, target_rps / 2.0),
            duration_sec=ramp_up_sec,
            stage_name="ramp_up",
        )
        # 2. Steady state (100% VUs & 100% RPS)
        s_steady = await run_load_stage(
            client,
            request_fn,
            vus=vus,
            target_rps=target_rps,
            duration_sec=steady_sec,
            stage_name="steady",
        )
        # 3. Ramp-down (50% VUs & 50% RPS)
        s_ramp_down = await run_load_stage(
            client,
            request_fn,
            vus=max(1, vus // 2),
            target_rps=max(1.0, target_rps / 2.0),
            duration_sec=ramp_down_sec,
            stage_name="ramp_down",
        )

    total_duration = round(time.perf_counter() - t0, 2)
    host_summary = monitor.stop()
    ensure_backend_healthy()

    all_latencies = s_ramp_up["_raw_latencies"] + s_steady["_raw_latencies"] + s_ramp_down["_raw_latencies"]
    for st in (s_ramp_up, s_steady, s_ramp_down):
        st.pop("_raw_latencies", None)

    overall_latency = compute_latency_stats(all_latencies)
    total_reqs = s_ramp_up["total_requests"] + s_steady["total_requests"] + s_ramp_down["total_requests"]
    total_errs = s_ramp_up["error_requests"] + s_steady["error_requests"] + s_ramp_down["error_requests"]
    overall_err_rate = round((total_errs / total_reqs) * 100.0, 3) if total_reqs > 0 else 0.0

    combined_status: dict[str, int] = {}
    for st in (s_ramp_up, s_steady, s_ramp_down):
        for k, v in st["status_counts"].items():
            combined_status[k] = combined_status.get(k, 0) + v

    extra_info = extra_checks_fn() if extra_checks_fn else {}

    # Đánh giá SLA dựa trên pha Steady-state và Overall
    steady_p95 = s_steady["latency"]["p95_ms"]
    passed_client_sla = (steady_p95 <= sla_p95_ms) and (s_steady["error_rate_pct"] <= sla_error_rate_pct)

    result = {
        "tc_id": tc_id,
        "title": title,
        "endpoint": endpoint_desc,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_duration_sec": total_duration,
        "config": {
            "vus": vus,
            "target_rps": target_rps,
            "ramp_up_sec": ramp_up_sec,
            "steady_sec": steady_sec,
            "ramp_down_sec": ramp_down_sec,
            "sla_p95_ms": sla_p95_ms,
            "sla_error_rate_pct": sla_error_rate_pct,
        },
        "overall": {
            "total_requests": total_reqs,
            "success_requests": total_reqs - total_errs,
            "error_requests": total_errs,
            "error_rate_pct": overall_err_rate,
            "actual_rps": round(total_reqs / max(0.001, total_duration), 2),
            "latency": overall_latency,
            "status_counts": combined_status,
        },
        "stages": {
            "ramp_up": s_ramp_up,
            "steady": s_steady,
            "ramp_down": s_ramp_down,
        },
        "host_resources": host_summary,
        "extra_checks": extra_info,
        "sla_evaluation": {
            "steady_p95_ms": steady_p95,
            "steady_error_rate_pct": s_steady["error_rate_pct"],
            "passed_client_sla": passed_client_sla,
            "verdict": "Passed" if passed_client_sla else "Failed",
        },
    }

    save_tc_result(tc_id, result)
    print(
        f"<<< Hoàn tất {tc_id}: Verdict={result['sla_evaluation']['verdict']} | "
        f"Steady p95={steady_p95}ms (SLA < {sla_p95_ms}ms) | "
        f"Err={s_steady['error_rate_pct']}% | RPS={s_steady['actual_rps']}"
    )
    return result


def save_tc_result(tc_id: str, data: dict[str, Any]) -> Path:
    target_dir = RESULTS_DIR / f"round_{PERF_ROUND}"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"{tc_id}.json"
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_file
