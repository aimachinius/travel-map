"""
Module dependencies: Quản lý vòng đời Singleton cho Pipeline, Hàng đợi, Cầu nối mạng và Khóa GPU Semaphore.
"""

import asyncio
import threading
from typing import Optional

from ..config.settings import ServerConfig, default_server_config
from .services.server_pipeline import ServerExtractionPipeline
from .services.job_manager import JobManager
from .services.tunnel_manager import TunnelManager
from ..utils.logger import get_logger

logger = get_logger("ServerDependencies")

# Khóa điều phối độc quyền GPU toàn diện (chống xung đột bộ nhớ giữa GPUDBNet và Vintern-1B)
GPU_SEMAPHORE = asyncio.Semaphore(1)
GPU_LOCK_SYNC = threading.Lock()

_server_config: Optional[ServerConfig] = None
_pipeline_instance: Optional[ServerExtractionPipeline] = None
_job_manager_instance: Optional[JobManager] = None
_tunnel_manager_instance: Optional[TunnelManager] = None


def get_server_config() -> ServerConfig:
    global _server_config
    if _server_config is None:
        _server_config = default_server_config
    return _server_config


def set_server_config(config: ServerConfig):
    global _server_config
    _server_config = config


def get_pipeline() -> ServerExtractionPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        cfg = get_server_config()
        _pipeline_instance = ServerExtractionPipeline(
            config=cfg,
            lazy_load_models=True,
            gpu_lock_sync=GPU_LOCK_SYNC,
        )
    return _pipeline_instance


def get_job_manager() -> JobManager:
    global _job_manager_instance
    if _job_manager_instance is None:
        _job_manager_instance = JobManager()
    return _job_manager_instance


def get_tunnel_manager() -> TunnelManager:
    global _tunnel_manager_instance
    if _tunnel_manager_instance is None:
        cfg = get_server_config()
        _tunnel_manager_instance = TunnelManager(
            port=cfg.port,
            provider=cfg.tunnel_provider,
            ngrok_authtoken=cfg.ngrok_authtoken,
            ngrok_domain=cfg.ngrok_domain,
        )
    return _tunnel_manager_instance


def get_gpu_semaphore() -> asyncio.Semaphore:
    return GPU_SEMAPHORE


def get_gpu_lock_sync() -> threading.Lock:
    return GPU_LOCK_SYNC
