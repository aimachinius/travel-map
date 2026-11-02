"""
Module test_tunnel_manager: Kiểm thử độc lập Module 6 - TunnelManager & Cổng Test Local.
"""

import unittest

from src.server.services.tunnel_manager import TunnelManager


class TestTunnelManager(unittest.TestCase):
    def test_local_only_mode(self):
        manager = TunnelManager(port=8000, provider="none")
        public_url = manager.start_tunnel()

        self.assertIsNone(public_url)
        urls = manager.get_access_urls()
        self.assertEqual(urls["local_url"], "http://127.0.0.1:8000")
        self.assertIsNone(urls["public_tunnel_url"])
        self.assertFalse(urls["is_tunnel_active"])

    def test_tunnel_initialization_attributes(self):
        manager = TunnelManager(port=8080, provider="cloudflare")
        self.assertEqual(manager.port, 8080)
        self.assertEqual(manager.provider, "cloudflare")
        urls = manager.get_access_urls()
        self.assertEqual(urls["local_url"], "http://127.0.0.1:8080")


if __name__ == "__main__":
    unittest.main()
