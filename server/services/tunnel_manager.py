"""
Module tunnel_manager: Quản lý cầu nối Internet công khai trên Google Colab qua Cloudflare Tunnel và Ngrok.
Duy trì song hành cổng truy cập nội bộ (http://127.0.0.1:8000) và đường dẫn HTTPS công khai.
"""

import os
import sys
import time
import threading
from typing import Dict, Any, Optional

from ...utils.logger import get_logger

logger = get_logger("TunnelManager")


class TunnelManager:
    """
    Điều phối mở cầu nối mạng công khai từ Google Colab hoặc máy chủ local ra Internet.
    """
    def __init__(
        self,
        port: int = 8000,
        provider: str = "cloudflare",
        ngrok_authtoken: Optional[str] = None,
        ngrok_domain: Optional[str] = None,
    ):
        self.port = port
        self.provider = str(provider).lower()
        self.ngrok_authtoken = ngrok_authtoken or os.environ.get("NGROK_AUTHTOKEN")
        self.ngrok_domain = ngrok_domain or os.environ.get("NGROK_DOMAIN")
        self.public_url: Optional[str] = None
        self._tunnel_obj = None

    def start_tunnel(self) -> Optional[str]:
        """Khởi động cầu nối mạng theo cấu hình provider."""
        if self.provider == "none":
            logger.info("Chế độ mạng: Chỉ mở cổng nội bộ Local (không mở cầu nối Public).")
            return None

        if self.provider == "cloudflare":
            return self._start_cloudflare()

        if self.provider == "ngrok":
            return self._start_ngrok()

        logger.warning(f"Provider cầu nối không hợp lệ: '{self.provider}'. Fallback về local-only.")
        return None

    def _start_cloudflare(self) -> Optional[str]:
        """Tạo Cloudflare Tunnel tự động (Miễn phí 100%, không cần token)."""
        logger.info(f"Đang khởi động Cloudflare Tunnel cho cổng local {self.port}...")
        try:
            from pycloudflared import try_cloudflare
            tunnel = try_cloudflare(port=self.port)
            self._tunnel_obj = tunnel
            self.public_url = getattr(tunnel, "tunnel", None) or getattr(tunnel, "tunnel_url", None) or str(tunnel)
            logger.info("=" * 60)
            logger.info("🎉 [CẦU NỐI CLOUDFLARE TUNNEL THÀNH CÔNG!]")
            logger.info(f"🌐 Public URL (HTTPS): {self.public_url}")
            logger.info(f"🏠 Local URL         : http://127.0.0.1:{self.port}")
            logger.info("=" * 60)
            return self.public_url
        except ImportError:
            logger.warning("Thư viện 'pycloudflared' chưa được cài đặt. Chạy: pip install pycloudflared")
        except Exception as e:
            logger.error(f"Lỗi khi khởi chạy Cloudflare Tunnel: {e}")
        return None

    def _start_ngrok(self) -> Optional[str]:
        """Tạo Ngrok Tunnel (Hỗ trợ cấu hình auth token & custom domain)."""
        logger.info(f"Đang khởi động Ngrok Tunnel cho cổng local {self.port}...")
        try:
            from pyngrok import ngrok
            if self.ngrok_authtoken:
                ngrok.set_auth_token(self.ngrok_authtoken)
            
            connect_kwargs = {"addr": self.port, "proto": "http"}
            if self.ngrok_domain:
                connect_kwargs["domain"] = self.ngrok_domain

            tunnel = ngrok.connect(**connect_kwargs)
            self._tunnel_obj = tunnel
            self.public_url = tunnel.public_url
            logger.info("=" * 60)
            logger.info("🎉 [CẦU NỐI NGROK TUNNEL THÀNH CÔNG!]")
            logger.info(f"🌐 Public URL (HTTPS): {self.public_url}")
            logger.info(f"🏠 Local URL         : http://127.0.0.1:{self.port}")
            logger.info("=" * 60)
            return self.public_url
        except ImportError:
            logger.warning("Thư viện 'pyngrok' chưa được cài đặt. Chạy: pip install pyngrok")
        except Exception as e:
            logger.error(f"Lỗi khi khởi chạy Ngrok Tunnel: {e}")
        return None

    def get_access_urls(self) -> Dict[str, Any]:
        """Trả về thông tin kết nối song hành: Cổng test nội bộ và Cầu nối công khai."""
        return {
            "local_url": f"http://127.0.0.1:{self.port}",
            "public_tunnel_url": self.public_url,
            "tunnel_provider": self.provider,
            "is_tunnel_active": bool(self.public_url),
        }

    def stop_tunnel(self):
        """Dừng cầu nối mạng khi tắt server."""
        if self.provider == "cloudflare":
            try:
                from pycloudflared import try_cloudflare
                try_cloudflare.terminate(self.port)
                logger.info("Đã đóng Cloudflare Tunnel.")
            except Exception:
                pass
        elif self.provider == "ngrok":
            try:
                from pyngrok import ngrok
                ngrok.kill()
                logger.info("Đã đóng Ngrok Tunnel.")
            except Exception:
                pass
        self.public_url = None
