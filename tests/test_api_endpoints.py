"""
Module test_api_endpoints: Kiểm thử tích hợp Module 8 - FastAPI Endpoints & Non-blocking Event Loop.
"""

import unittest
from fastapi.testclient import TestClient

from src.server.app import app
from src.server.dependencies import set_server_config
from src.config.settings import ServerConfig


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Thiết lập server config cho môi trường test (không mở tunnel thật)
        test_config = ServerConfig(tunnel_provider="none")
        set_server_config(test_config)
        cls.client = TestClient(app)

    def test_health_check_endpoint(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertIn("access_urls", data)
        self.assertEqual(data["access_urls"]["local_url"], "http://127.0.0.1:8000")
        self.assertIn("gpu_available", data)

    def test_health_alias_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "HEALTHY")

    def test_extract_empty_url_returns_400(self):
        payload = {"url": ""}
        response = self.client.post("/api/v1/extract", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("không được để trống", response.json()["detail"])

    def test_extract_unsupported_platform_returns_400(self):
        payload = {"url": "https://www.facebook.com/watch/?v=123456789"}
        response = self.client.post("/api/v1/extract", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("không được hỗ trợ", response.json()["detail"])

    def test_async_job_creation_and_polling(self):
        # 1. Tạo Job
        payload = {"url": "https://www.youtube.com/shorts/kJQP7kiw5Fk"}
        create_res = self.client.post("/api/v1/jobs", json=payload)
        self.assertEqual(create_res.status_code, 202)
        job_data = create_res.json()
        self.assertIn("job_id", job_data)
        job_id = job_data["job_id"]

        # 2. Thăm dò trạng thái qua ID
        status_res = self.client.get(f"/api/v1/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)
        info = status_res.json()
        self.assertEqual(info["job_id"], job_id)
        self.assertIn(info["status"], ["QUEUED", "DOWNLOADING", "TRANSCRIBING", "VLM_INFERENCE", "COMPLETED", "FAILED"])

    def test_get_non_existent_job_returns_404(self):
        response = self.client.get("/api/v1/jobs/job_non_existent_9999")
        self.assertEqual(response.status_code, 404)

    def test_list_recent_jobs(self):
        response = self.client.get("/api/v1/jobs")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main()
