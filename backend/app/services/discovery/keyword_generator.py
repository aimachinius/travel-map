"""Orthogonal keyword generator for administrative unit discovery.

Strictly extracts administrative names from ward/commune level up (ward, district, city)
and avoids POI (points of interest), school, or venue names.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def clean_admin_name(name: Optional[str]) -> Optional[str]:
    """Clean administrative prefixes like 'Phường ', 'Xã ', 'Quận ', 'Huyện ', 'Thành phố ', 'Tỉnh '

    to create natural search phrases (e.g., 'Phường Hòa Khánh Nam' -> 'Hòa Khánh Nam').
    """
    if not name:
        return None
    name_str = str(name).strip()
    if not name_str:
        return None

    # Remove common prefixes for search phrasing
    cleaned = re.sub(
        r"^(phường|xã|thị trấn|thị xã|quận|huyện|thành phố|tỉnh|tp\.)\s+",
        "",
        name_str,
        flags=re.IGNORECASE,
    ).strip()

    # Protect numbered administrative units like "Quận 1", "Quận 3", "Phường 10"
    if cleaned.isdigit():
        return name_str

    return cleaned or name_str


def generate_orthogonal_keywords(
    current_address: Dict[str, Any],
    coverage_items: Optional[List[Dict[str, Any]]] = None,
    max_keywords: int = 6,
) -> List[str]:
    """Generate orthogonal food discovery keywords based solely on administrative units (ward, district, city).

    Categorizes into 3 distinct food domains to minimize video overlap:
      1. Nhóm món ăn / bữa chính: 'quán ăn ở [Địa danh]'
      2. Nhóm đồ uống / cafe: 'quán cafe ở [Địa danh]'
      3. Nhóm ăn vặt: 'ăn vặt [Địa danh]'

    Rules:
      - STRICTLY administrative units from ward/commune level up (ward, district, city).
      - NEVER uses POIs (schools, restaurants, private venues) or streets.
      - Selects 1 representative variant per category per administrative unit.

    Args:
        current_address: Dict containing 'ward', 'district', 'city', 'country' from resolve_current_address.
        coverage_items: Optional list of intersecting administrative items from DistrictCoverageService.
        max_keywords: Maximum number of keywords to return (default: 6).

    Returns:
        List of orthogonal search keyword strings.
    """
    raw_ward = current_address.get("ward")
    raw_district = current_address.get("district")
    raw_city = current_address.get("city")

    ward = clean_admin_name(raw_ward)
    district = clean_admin_name(raw_district)
    city = clean_admin_name(raw_city)

    # Collect administrative targets in priority order: [Ward, District, Coverage items, City]
    admin_targets: List[str] = []

    if ward and city:
        admin_targets.append(f"{ward} {city}")
    elif ward:
        admin_targets.append(ward)

    if district and city and district != ward:
        admin_targets.append(f"{district} {city}")
    elif district and district != ward:
        admin_targets.append(district)

    # Add top intersecting administrative units from coverage if available
    if coverage_items:
        for item in coverage_items:
            item_name = clean_admin_name(item.get("name"))
            pct = item.get("percentage", 0.0)
            # Only consider significant coverage (>= 5%)
            if item_name and pct >= 5.0:
                combined_name = f"{item_name} {city}" if city and city.lower() not in item_name.lower() else item_name
                if combined_name not in admin_targets and item_name not in [ward, district]:
                    admin_targets.append(combined_name)

    # Fallback to city alone if no ward/district identified
    if not admin_targets and city:
        admin_targets.append(city)

    if not admin_targets:
        admin_targets.append("Đà Nẵng")

    # Categories to generate: (Food, Cafe, Snacks)
    category_templates = [
        ("food", "quán ăn ở {target}"),
        ("cafe", "quán cafe ở {target}"),
        ("snack", "ăn vặt {target}"),
    ]

    generated: List[str] = []

    # Round-robin generation across administrative targets to ensure balanced categories
    for cat_name, template in category_templates:
        for target in admin_targets:
            kw = template.format(target=target)
            if kw not in generated:
                generated.append(kw)
                break  # Pick 1 representative target per category before moving to next target
        if len(generated) >= max_keywords:
            break

    # If space remains, add secondary administrative units
    if len(generated) < max_keywords:
        for target in admin_targets[1:]:
            for cat_name, template in category_templates:
                kw = template.format(target=target)
                if kw not in generated:
                    generated.append(kw)
                if len(generated) >= max_keywords:
                    break
            if len(generated) >= max_keywords:
                break

    return generated[:max_keywords]

