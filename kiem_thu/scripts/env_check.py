import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import httpx
import paramiko
import psutil
import psycopg
import redis

BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

AI_TUNNEL_URL = "https://funk-smooth-alive-hosting.trycloudflare.com/api/v1/extract"
AI_TUNNEL_BASE = "https://funk-smooth-alive-hosting.trycloudflare.com"
SSH_HOST = "2.tcp.us-cal-1.ngrok.io"
SSH_PORT = 10083
SSH_USER = "nippon"
SSH_PASS = "nippon"


def check_host_system() -> dict:
    vm = psutil.virtual_memory()
    cpu_freq = psutil.cpu_freq()
    disk = psutil.disk_usage(str(BASE_DIR))
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "os": platform.platform(),
        "processor": platform.processor(),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": cpu_freq.current if cpu_freq else None,
        "cpu_usage_percent": psutil.cpu_percent(interval=1.0),
        "ram_total_mb": round(vm.total / (1024 * 1024), 2),
        "ram_available_mb": round(vm.available / (1024 * 1024), 2),
        "ram_used_mb": round(vm.used / (1024 * 1024), 2),
        "ram_percent": vm.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
    }


def check_docker_containers() -> list[dict]:
    try:
        res = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        containers = []
        for line in res.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) == 4:
                containers.append(
                    {
                        "name": parts[0],
                        "cpu_percent": parts[1],
                        "mem_usage": parts[2],
                        "mem_percent": parts[3],
                    }
                )
        return containers
    except Exception as e:
        return [{"error": str(e)}]


def check_postgres() -> dict:
    try:
        conn = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/foodspot_db")
        with conn.cursor() as cur:
            cur.execute("SHOW max_connections;")
            max_conn = cur.fetchone()[0]
            cur.execute("SHOW shared_buffers;")
            shared_buffers = cur.fetchone()[0]

            tables = [
                "users",
                "places",
                "videos",
                "video_place_matches",
                "analysis_runs",
                "saved_places",
                "saved_videos",
                "discovery_scans",
            ]
            counts = {}
            for t in tables:
                cur.execute(f"SELECT count(*) FROM {t};")
                counts[t] = cur.fetchone()[0]

            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname;
                """
            )
            indexes = [{"name": r[0], "def": r[1]} for r in cur.fetchall()]
        conn.close()
        return {
            "status": "ok",
            "max_connections": max_conn,
            "shared_buffers": shared_buffers,
            "table_counts": counts,
            "indexes": indexes,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_redis() -> dict:
    try:
        r = redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
        info = r.info("memory")
        q_high = r.llen("queue:high_priority")
        q_low = r.llen("queue:low_priority")
        r.close()
        return {
            "status": "ok",
            "used_memory_human": info.get("used_memory_human"),
            "used_memory_peak_human": info.get("used_memory_peak_human"),
            "maxmemory_human": info.get("maxmemory_human"),
            "queue_high_priority_len": q_high,
            "queue_low_priority_len": q_low,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_ai_tunnel() -> dict:
    result = {"extract_url": AI_TUNNEL_URL}
    for path in ["/health", "/docs", "/openapi.json"]:
        try:
            resp = httpx.get(f"{AI_TUNNEL_BASE}{path}", timeout=10.0)
            result[path] = {
                "status_code": resp.status_code,
                "body_preview": resp.text[:1000],
            }
        except Exception as e:
            result[path] = {"error": str(e)}
    return result


def check_ai_ssh() -> dict:
    ssh_log_lines = []
    out_data = {"host": SSH_HOST, "port": SSH_PORT, "status": "unknown", "commands": {}}
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASS,
            timeout=15,
        )
        out_data["status"] = "connected"
        commands = [
            "uname -a",
            "LD_LIBRARY_PATH=/usr/lib64-nvidia:/usr/local/nvidia/lib64 /opt/bin/nvidia-smi",
            "free -m",
            "df -h",
            "ps aux | grep -E 'python|uvicorn|cloudflared|ngrok' | grep -v grep",
            "ls -la /content",
        ]
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
            out_str = stdout.read().decode("utf-8", errors="replace").strip()
            err_str = stderr.read().decode("utf-8", errors="replace").strip()
            out_data["commands"][cmd] = {"stdout": out_str, "stderr": err_str}
            ssh_log_lines.append(f"=== [{datetime.datetime.now().isoformat()}] $ {cmd} ===")
            ssh_log_lines.append(out_str)
            if err_str:
                ssh_log_lines.append(f"[STDERR] {err_str}")
            ssh_log_lines.append("")
        ssh.close()
    except Exception as e:
        out_data["status"] = "error"
        out_data["error"] = str(e)
        ssh_log_lines.append(f"SSH Connection Error: {e}")

    ssh_log_file = LOGS_DIR / "ai_server_ssh_audit.log"
    ssh_log_file.write_text("\n".join(ssh_log_lines), encoding="utf-8")
    return out_data


def main():
    print("Đang kiểm tra môi trường Host, Docker, PostgreSQL, Redis, Cloudflare Tunnel & SSH AI Server...")
    report = {
        "host": check_host_system(),
        "docker": check_docker_containers(),
        "postgres": check_postgres(),
        "redis": check_redis(),
        "ai_tunnel": check_ai_tunnel(),
        "ai_ssh": check_ai_ssh(),
    }
    audit_path = RESULTS_DIR / "env_audit.json"
    audit_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Đã lưu báo cáo kiểm tra môi trường tại: {audit_path}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
