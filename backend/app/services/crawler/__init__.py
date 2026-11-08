"""Crawler package for extracting video links from social media platforms."""

from .tiktok_crawler import crawl_tiktok_links, crawl_tiktok_links_async

__all__ = ["crawl_tiktok_links", "crawl_tiktok_links_async"]

