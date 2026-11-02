"""
Package pipeline: Chứa pipeline hợp nhất trích xuất quán ăn.
"""

from .restaurant_pipeline import RestaurantExtractorPipeline, RestaurantExtractionResult

__all__ = ["RestaurantExtractorPipeline", "RestaurantExtractionResult"]
