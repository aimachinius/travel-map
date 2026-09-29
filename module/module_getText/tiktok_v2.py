import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import requests
from playwright.sync_api import sync_playwright


# Số comment lấy trong MỖI request TikTok.
# Mỗi batch sẽ được xử lý ngay trước khi lấy batch tiếp theo.
COMMENT_BATCH_SIZE = 20
COMMENTS_PER_REQUEST = COMMENT_BATCH_SIZE

# Số reply lấy trong mỗi request khi cần kiểm tra thread.
REPLIES_PER_REQUEST = 20

# Lấy tối đa 2 địa chỉ ứng viên từ comment/reply.
MAX_ADDRESSES = 3 

MODEL_SERVER_URL = os.getenv(
    "LOCATION_MODEL_URL",
    "http://127.0.0.1:8000/classify",
)
MODEL_TIMEOUT = 20

# ============================================================
# VIDEO DOWNLOAD MODE
# ============================================================
# True  = tải video TikTok về
# False = không tải video
DOWNLOAD_VIDEO = False

# Thư mục lưu video khi DOWNLOAD_VIDEO = True
VIDEO_OUTPUT_DIR = "videos"


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================
# GENERAL HELPERS
# ============================================================


def extract_video_id(url):
    match = re.search(r"/video/(\d+)", url)
    if not match:
        raise ValueError("Không tìm thấy TikTok video ID trong URL.")
    return match.group(1)


def extract_place_id(place_url):
    if not place_url:
        return None

    match = re.search(r"/place/.*?-(\d+)", place_url)
    if match:
        return match.group(1)

    match = re.search(r"/place/(\d+)", place_url)
    if match:
        return match.group(1)

    return None


def extract_plus_code(address):
    if not address:
        return None

    match = re.search(
        r"\b([A-Z0-9]{4,8}\+[A-Z0-9]{2,4})\b",
        address,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    return None


def parse_address_components(address):
    city = ""
    country = ""

    if not address:
        return city, country

    parts = [
        p.strip()
        for p in address.split(",")
        if p.strip()
    ]

    if parts:
        country = parts[-1]

        if len(parts) >= 2:
            city_part = parts[-2]
            city = re.sub(r"\d+", "", city_part).strip()

    return city, country


def clean_text(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def get_author(comment):
    user = comment.get("user") or {}

    if isinstance(user, dict):
        return clean_text(
            user.get("unique_id")
            or user.get("nickname")
            or user.get("uid")
            or "Unknown"
        )

    return "Unknown"


def get_comment_text(comment):
    return clean_text(comment.get("text") or "")


def get_like_count(comment):
    return safe_int(comment.get("digg_count") or 0)


def extract_comment_id(comment):
    return comment.get("cid") or comment.get("id")


# ============================================================
# TIKTOK API VIA PLAYWRIGHT PAGE
# ============================================================


def fetch_json_from_tiktok(page, endpoint, params):
    result = page.evaluate(
        """
        async ({endpoint, params}) => {
            const url = new URL(
                endpoint,
                window.location.origin
            );

            for (const [key, value] of Object.entries(params)) {
                url.searchParams.set(key, String(value));
            }

            const response = await fetch(
                url.toString(),
                {
                    method: "GET",
                    credentials: "include"
                }
            );

            const text = await response.text();

            return {
                status: response.status,
                contentType: response.headers.get("content-type") || "",
                text: text
            };
        }
        """,
        {
            "endpoint": endpoint,
            "params": params,
        },
    )

    status = result["status"]
    content_type = result["contentType"]
    text = result["text"]

    if status != 200:
        raise RuntimeError(
            f"TikTok API HTTP {status}\nResponse: {text[:500]}"
        )

    if "json" not in content_type.lower():
        raise RuntimeError(
            "TikTok không trả JSON.\n"
            f"HTTP: {status}\n"
            f"Content-Type: {content_type}\n"
            f"Response đầu: {text[:300]}"
        )

    try:
        return json.loads(text)
    except Exception as exc:
        raise RuntimeError(
            f"Không parse được JSON từ TikTok: {exc}"
        )


# ============================================================
# DESCRIPTION + PLACE
# ============================================================


def get_description(page):
    try:
        script_text = page.locator(
            "#__UNIVERSAL_DATA_FOR_REHYDRATION__"
        ).inner_text(timeout=2000)

        if script_text:
            data = json.loads(script_text)
            desc = (
                data.get("__DEFAULT_SCOPE__", {})
                .get("webapp.video-detail", {})
                .get("itemInfo", {})
                .get("itemStruct", {})
                .get("desc")
            )

            if desc:
                return clean_text(desc)
    except Exception:
        pass

    try:
        value = page.locator(
            'meta[property="og:description"]'
        ).get_attribute("content", timeout=2000)

        if value:
            return clean_text(value)
    except Exception:
        pass

    try:
        value = page.locator(
            'meta[name="description"]'
        ).get_attribute("content", timeout=2000)

        if value:
            return clean_text(value)
    except Exception:
        pass

    try:
        desc_el = page.locator(
            '[data-e2e="browse-video-desc"], '
            '[data-e2e="user-post-item-desc"]'
        )

        if desc_el.count() > 0:
            value = desc_el.first.inner_text(timeout=2000)

            if value:
                return clean_text(value)
    except Exception:
        pass

    return ""


def get_video_poi(page):
    try:
        script_text = page.locator(
            "#__UNIVERSAL_DATA_FOR_REHYDRATION__"
        ).inner_text(timeout=2000)

        if script_text:
            data = json.loads(script_text)
            poi = (
                data.get("__DEFAULT_SCOPE__", {})
                .get("webapp.video-detail", {})
                .get("itemInfo", {})
                .get("itemStruct", {})
                .get("poi")
            )

            if poi and isinstance(poi, dict):
                return poi
    except Exception:
        pass

    return None


def get_places(page):
    places = []
    seen = set()

    try:
        links = page.locator('a[href*="/place/"]')
        count = links.count()
        print(f"  → Found {count} place link(s)")

        for i in range(count):
            link = links.nth(i)
            href = link.get_attribute("href")
            name = clean_text(link.inner_text())

            if not href:
                continue

            if href.startswith("/"):
                href = "https://www.tiktok.com" + href

            if href in seen:
                continue

            seen.add(href)
            places.append({
                "name": name,
                "url": href,
            })
    except Exception as exc:
        print(f"  ⚠ Warning reading place links: {exc}")

    return places


def get_place_details(context, place_url, known_poi=None):
    page = context.new_page()

    place_details = {
        "source": "tiktok",
        "place_id": extract_place_id(place_url),
        "name": "",
        "tiktok_url": place_url,
        "area": "",
        "category": "",
        "address": "",
        "plus_code": None,
        "video_count": "",
        "geocoding": {
            "latitude": None,
            "longitude": None,
            "formatted_address": None,
            "google_maps_url": None,
        },
    }

    if known_poi:
        place_details["name"] = clean_text(
            known_poi.get("name") or ""
        )
        place_details["area"] = clean_text(
            known_poi.get("city")
            or known_poi.get("fatherPoiName")
            or ""
        )
        place_details["category"] = clean_text(
            known_poi.get("ttTypeNameMedium")
            or known_poi.get("ttTypeNameTiny")
            or known_poi.get("category")
            or ""
        )
        place_details["address"] = clean_text(
            known_poi.get("address") or ""
        )

        if known_poi.get("id"):
            place_details["place_id"] = str(
                known_poi.get("id")
            )

    try:
        print(f"  → Opening place page: {place_url}")

        page.goto(
            place_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        try:
            page.wait_for_selector(
                "h1",
                timeout=6000,
            )
        except Exception:
            page.wait_for_timeout(3000)

        if not place_details["name"]:
            try:
                h1_text = page.locator(
                    "h1"
                ).first.inner_text(timeout=2000)

                if h1_text:
                    place_details["name"] = clean_text(
                        h1_text
                    )
            except Exception:
                pass

        try:
            body_text = page.locator(
                "body"
            ).inner_text(timeout=2000)

            lines = [
                line.strip()
                for line in body_text.splitlines()
                if line.strip()
            ]

            v_match = re.search(
                r"(\d[\d,\.]*\s*[KMkm]?\s*videos?)",
                body_text,
                re.IGNORECASE,
            )

            if v_match:
                place_details["video_count"] = clean_text(
                    v_match.group(1)
                )

            if not place_details["area"]:
                for line in lines:
                    if re.search(
                        r"videos?",
                        line,
                        re.IGNORECASE,
                    ):
                        candidate_area = re.sub(
                            r"\d[\d,\.]*\s*[KMkm]?\s*videos?.*$",
                            "",
                            line,
                            flags=re.IGNORECASE,
                        ).strip()

                        if candidate_area:
                            place_details["area"] = clean_text(
                                candidate_area
                            )
                            break

            if not place_details["address"]:
                for line in lines:
                    if re.search(
                        r"\b[A-Z0-9]{4,8}\+[A-Z0-9]{2,4}\b",
                        line,
                    ):
                        place_details["address"] = clean_text(
                            line
                        )
                        break
        except Exception:
            pass

    except Exception as exc:
        print(
            f"  ⚠ Warning loading place page: {exc}"
        )
    finally:
        try:
            page.close()
        except Exception:
            pass

    if place_details["address"]:
        place_details["plus_code"] = extract_plus_code(
            place_details["address"]
        )

    if not place_details["name"]:
        slug_match = re.search(
            r"/place/([a-zA-Z0-9\-]+)-\d+",
            place_url,
        )

        if slug_match:
            place_details["name"] = (
                slug_match.group(1)
                .replace("-", " ")
            )

    return place_details


def geocode_place(
    name,
    address=None,
    area=None,
    city=None,
    country=None,
):
    clean_addr = ""

    if address:
        clean_addr = re.sub(
            r"^[A-Z0-9]{4,8}\+[A-Z0-9]{2,4}[,\s]*",
            "",
            address,
        ).strip()

    candidates = []

    if name and clean_addr:
        candidates.append(f"{name}, {clean_addr}")

    if name and city and country:
        candidates.append(f"{name}, {city}, {country}")

    if name and area and country:
        candidates.append(f"{name}, {area}, {country}")

    if name and country:
        candidates.append(f"{name}, {country}")

    if name and (city or area):
        candidates.append(f"{name}, {city or area}")

    if name:
        candidates.append(name)

    if clean_addr:
        candidates.append(clean_addr)

    headers = {
        "User-Agent": (
            "PBL6-TikTok-Location-Research/1.0"
        )
    }

    seen_q = set()

    for query in candidates:
        if not query or query in seen_q:
            continue

        seen_q.add(query)

        try:
            url = (
                "https://nominatim.openstreetmap.org/search?"
                + urllib.parse.urlencode({
                    "q": query,
                    "format": "json",
                    "limit": 1,
                })
            )

            req = urllib.request.Request(
                url,
                headers=headers,
            )

            with urllib.request.urlopen(
                req,
                timeout=10,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            if data:
                result = data[0]
                lat = float(result["lat"])
                lon = float(result["lon"])

                return {
                    "latitude": lat,
                    "longitude": lon,
                    "formatted_address": result.get(
                        "display_name",
                        "",
                    ),
                    "google_maps_url": (
                        "https://www.google.com/maps/search/?api=1"
                        f"&query={lat},{lon}"
                    ),
                    "query_used": query,
                }

        except Exception:
            pass

        time.sleep(1)

    return {
        "latitude": None,
        "longitude": None,
        "formatted_address": None,
        "google_maps_url": None,
    }


# ============================================================
# COMMENTS + REPLIES
# ============================================================


def get_comments_batch(page, video_id, cursor=0, seen_ids=None):
    """Fetch ONE batch of top-level comments.

    Không tải toàn bộ comments một lần. Mỗi lần gọi chỉ lấy tối đa
    COMMENTS_PER_REQUEST comment rồi trả cursor để caller xử lý batch
    trước khi lấy batch tiếp theo.
    """
    if seen_ids is None:
        seen_ids = set()

    print(
        f"  → Request comments (cursor={cursor})..."
    )

    params = {
        "aid": "1988",
        "aweme_id": video_id,
        "count": COMMENTS_PER_REQUEST,
        "cursor": cursor,
    }

    data = fetch_json_from_tiktok(
        page,
        "/api/comment/list/",
        params,
    )

    page_comments = data.get("comments") or []
    print(
        f"    Received: {len(page_comments)}"
    )

    comments = []
    for comment in page_comments:
        comment_id = extract_comment_id(comment)

        if comment_id is None:
            continue

        comment_id = str(comment_id)

        if comment_id in seen_ids:
            continue

        seen_ids.add(comment_id)
        comments.append(comment)

    has_more = bool(data.get("has_more", False))
    next_cursor = data.get("cursor", cursor)

    return comments, next_cursor, has_more

def get_replies(page, video_id, comment):
    """Fetch ALL replies for a comment (no cap). Paginate until has_more=False."""
    comment_id = extract_comment_id(comment)

    if not comment_id:
        return []

    print(
        f"    → Replies for comment {comment_id}"
    )

    replies = []
    seen_ids = set()
    cursor = 0

    while True:
        params = {
            "aid": "1988",
            "item_id": video_id,
            "comment_id": comment_id,
            "count": REPLIES_PER_REQUEST,
            "cursor": cursor,
        }

        try:
            data = fetch_json_from_tiktok(
                page,
                "/api/comment/list/reply/",
                params,
            )
        except Exception as exc:
            print(
                f"      ⚠ Reply error: {exc}"
            )
            break

        page_replies = data.get("comments") or []

        for reply in page_replies:
            reply_id = extract_comment_id(reply)
            if reply_id is None:
                continue
            reply_id = str(reply_id)
            if reply_id in seen_ids:
                continue
            seen_ids.add(reply_id)
            replies.append(reply)

        if not bool(data.get("has_more", False)):
            break

        new_cursor = data.get("cursor", cursor)
        if new_cursor == cursor:
            break

        cursor = new_cursor
        time.sleep(0.3)

    return replies


# ============================================================
# MODEL SERVER CLIENT
# ============================================================


def classify_comment(session, text):
    """Gọi /classify — chỉ trả related=True/False."""
    response = session.post(
        MODEL_SERVER_URL,
        json={"text": text},
        timeout=MODEL_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def classify_comment_full(session, text):
    """
    Gọi /classify_full — trả cả related + address_type trong 1 request.
    address_type: PROVIDES | ASKS | UNCLEAR | NOT_LOCATION
    """
    url = MODEL_SERVER_URL.rsplit("/", 1)[0] + "/classify_full"
    response = session.post(
        url,
        json={"text": text},
        timeout=MODEL_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def check_model_server(session):
    health_url = MODEL_SERVER_URL.rsplit(
        "/",
        1,
    )[0] + "/health"

    try:
        response = session.get(
            health_url,
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise RuntimeError(
            "Không kết nối được Location Model Server. "
            "Hãy chạy: python location_filter_server.py\n"
            f"URL: {MODEL_SERVER_URL}\n"
            f"Lỗi: {exc}"
        )


def analyze_comments_with_model(
    page,
    video_id,
    comments,
    session,
    start_index=1,
    address_count=0,
    seen_address_texts=None,
):
    """Phân tích MỘT batch comment vừa fetch được.

    Batch hiện tại được xử lý xong trước khi caller lấy cursor tiếp theo.
    Hàm trả lại trạng thái địa chỉ để vòng lặp streaming tiếp tục.

    Với mỗi comment:
      1. Gọi /classify_full — xác định related + address_type.
      2. Nếu KHÔNG related → bỏ qua (không lấy reply).
      3. Nếu related + PROVIDES → lấy ngay comment.
      4. Nếu related + ASKS/UNCLEAR → lấy reply và tìm PROVIDES.

    Dừng toàn bộ workflow khi tìm đủ MAX_ADDRESSES địa chỉ khác nhau.
    """

    if seen_address_texts is None:
        seen_address_texts = set()

    analyzed_threads = []
    batch_end = start_index + len(comments) - 1

    print(
        f"\n  → Processing batch: comment "
        f"{start_index}–{batch_end} ({len(comments)} comment)..."
    )

    for local_index, comment in enumerate(comments, start=0):
        global_idx = start_index + local_index
        text = get_comment_text(comment)

        # --- Bước 1: phân loại comment gốc ---
        try:
            root_result = classify_comment_full(session, text)
        except Exception as exc:
            raise RuntimeError(
                f"Model server lỗi comment {global_idx}: {exc}"
            )

        related = root_result.get("related", False)
        address_type = root_result.get("address_type", "NOT_LOCATION")

        analyzed_replies = []
        relevant_replies = []
        address_replies = []
        thread_has_address = False

        if not related:
            # Không liên quan → bỏ qua, không lấy reply
            status = "DROP"

        elif address_type == "PROVIDES":
            # Comment gốc đã cung cấp địa chỉ.
            address_key = clean_text(text).casefold()

            if address_key and address_key not in seen_address_texts:
                seen_address_texts.add(address_key)
                address_count += 1
                thread_has_address = True
                status = "ADDRESS✓"
            elif address_key:
                # Có PROVIDES nhưng là text đã trùng.
                status = "DUPLICATE"
            else:
                status = "DROP(empty)"

        else:
            # Related + ASKS/UNCLEAR → kiểm tra reply
            replies = get_replies(page, video_id, comment)

            for r_idx, reply in enumerate(replies, start=1):
                reply_text = get_comment_text(reply)

                try:
                    reply_result = classify_comment_full(session, reply_text)
                except Exception as exc:
                    print(f"      ⚠ Reply {r_idx} error: {exc}")
                    reply_result = {
                        "related": False,
                        "address_type": "NOT_LOCATION",
                        "positive_score": 0,
                        "provider_score": 0,
                    }

                provides = (
                    reply_result.get("address_type") == "PROVIDES"
                )

                analyzed_replies.append({
                    "reply": reply,
                    "model": reply_result,
                    "provides_address": provides,
                })

                if provides:
                    reply_key = clean_text(reply_text).casefold()

                    if reply_key and reply_key not in seen_address_texts:
                        seen_address_texts.add(reply_key)
                        address_count += 1
                        thread_has_address = True

                    # Đủ số địa chỉ rồi thì không cần classify reply tiếp.
                    if address_count >= MAX_ADDRESSES:
                        break

            relevant_replies = [
                r for r in analyzed_replies
                if r["model"].get("related")
            ]
            address_replies = [
                r for r in analyzed_replies
                if r["provides_address"]
            ]

            status = "ADDRESS✓" if thread_has_address else "DROP(no answer)"

        # Chỉ giữ thread có ít nhất một địa chỉ thật sự được cung cấp.
        keep_thread = (
            bool(address_type == "PROVIDES" and thread_has_address)
            or bool(address_replies)
        )

        if keep_thread:
            analyzed_threads.append({
                "comment": comment,
                "model": root_result,
                "replies": analyzed_replies,
                "keep_thread": True,
                "root_related": related,
                "root_provides": address_type == "PROVIDES",
                "relevant_replies": relevant_replies,
                "address_replies": address_replies,
                "thread_has_address": thread_has_address,
            })

        print(
            f"  [{global_idx:03d}] {status:<12} "
            f"type={address_type:<12} "
            f"addr_replies={len(address_replies)} | "
            f"{text[:70]}"
        )

        if address_count >= MAX_ADDRESSES:
            print(
                f"\n  ✅ Đã tìm đủ {MAX_ADDRESSES} địa chỉ ứng viên!"
            )
            break

    return (
        analyzed_threads,
        address_count,
        seen_address_texts,
    )


# ============================================================
# VIDEO DOWNLOAD
# ============================================================


def download_video(video_url, video_id, output_dir):
    """
    Tải video TikTok bằng yt-dlp.

    Yêu cầu:
        pip install -U yt-dlp

    Video sẽ được lưu dưới dạng MP4 nếu yt-dlp/ffmpeg hỗ trợ merge.
    """
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(
        output_dir,
        f"{video_id}.%(ext)s",
    )

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        video_url,
    ]

    print("  → Downloading TikTok video...")
    print(f"     Output directory: {output_dir}")

    try:
        import subprocess

        result = subprocess.run(
            command,
            check=False,
        )
    except Exception as exc:
        raise RuntimeError(
            "Không thể chạy yt-dlp. Hãy cài bằng: "
            "python -m pip install -U yt-dlp"
            f"\nChi tiết: {exc}"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            "yt-dlp tải video thất bại. "
            "Kiểm tra URL, yt-dlp và ffmpeg."
        )

    print("  ✓ Video downloaded successfully")


# ============================================================
# OUTPUT
# ============================================================


def format_comment(comment, model_result, index):
    lines = []

    lines.append(
        f"{index:02d}. 👍 {get_like_count(comment):,}"
    )
    lines.append(
        f"    👤 {get_author(comment)}"
    )
    lines.append(
        f"    {get_comment_text(comment)}"
    )
    lines.append(
        f"    Model score: {model_result.get('positive_score', 0):.3f}"
    )

    return lines


def save_results(
    video_id,
    video_url,
    description,
    places,
    analyzed_threads,
    output_dir,
):
    """
    Lưu output rút gọn, CHỈ gồm:
      - DESCRIPTION
      - location: Name, Area, Address
      - comments: chỉ nội dung comment/reply thực sự cung cấp địa chỉ

    Logic lọc comment/reply phía trên không thay đổi.
    """

    os.makedirs(output_dir, exist_ok=True)

    txt_path = os.path.join(
        output_dir,
        f"{video_id}_comments.txt",
    )

    json_path = os.path.join(
        output_dir,
        f"{video_id}_data.json",
    )

    # =========================================================
    # LOCATION: chỉ giữ Name / Area / Address
    # =========================================================
    compact_locations = []

    for place in places:
        compact_locations.append({
            "Name": place.get("name") or "",
            "Area": place.get("area") or "",
            "Address": place.get("address") or "",
        })

    # =========================================================
    # COMMENTS: chỉ lấy comment/reply có địa chỉ
    #
    # Trường hợp 1:
    #   Root comment = PROVIDES
    #   -> lấy ngay text của root comment
    #
    # Trường hợp 2:
    #   Root comment = ASKS/UNCLEAR
    #   + reply = PROVIDES
    #   -> lấy ngay text của reply đó
    #
    # Không lấy:
    #   - comment chỉ hỏi địa chỉ
    #   - reply không cung cấp địa chỉ
    #   - score/model/author/likes
    # =========================================================
    address_comments = []
    seen_texts = set()

    for item in analyzed_threads:
        root_comment = item.get("comment") or ""
        root_provides = bool(item.get("root_provides"))

        # Root comment tự cung cấp địa chỉ
        if root_provides:
            text = get_comment_text(root_comment)

            if text and text not in seen_texts:
                address_comments.append(text)
                seen_texts.add(text)

        # Reply cung cấp địa chỉ
        for reply_item in item.get("address_replies", []):
            reply = reply_item.get("reply") or {}
            text = get_comment_text(reply)

            if text and text not in seen_texts:
                address_comments.append(text)
                seen_texts.add(text)

    # =========================================================
    # TXT OUTPUT
    # =========================================================
    lines = []

    lines.append(f"DESCRIPTION: {description or ''}")
    lines.append("")
    lines.append("LOCATION:")

    if compact_locations:
        for idx, location in enumerate(compact_locations, start=1):
            lines.append(f"[{idx}]")
            lines.append(f"Name: {location['Name']}")
            lines.append(f"Area: {location['Area']}")
            lines.append(f"Address: {location['Address']}")
            lines.append("")
    else:
        lines.append("None")
        lines.append("")

    lines.append("COMMENTS_WITH_ADDRESS:")

    if address_comments:
        for comment_text in address_comments:
            lines.append(f"- {comment_text}")
    else:
        lines.append("None")

    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))

    # =========================================================
    # JSON OUTPUT
    # =========================================================
    json_data = {
        "DESCRIPTION": description or "",
        "location": compact_locations,
        "comments": address_comments,
    }

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(
            json_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return (
        txt_path,
        json_path,
        len(address_comments),
        len(compact_locations),
    )


# ============================================================
# MAIN
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract TikTok description, places, comments and "
            "filter location-related comments with a local model server."
        )
    )

    parser.add_argument(
        "url",
        help="TikTok video URL",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="comments",
        help="Output directory (default: comments)",
    )

    args = parser.parse_args()

    video_id = extract_video_id(args.url)

    # ------------------------------------
    # OPTIONAL VIDEO DOWNLOAD
    # ------------------------------------
    if DOWNLOAD_VIDEO:
        video_dir = os.path.join(args.output, VIDEO_OUTPUT_DIR)
        print("\n[0/6] Downloading TikTok video...")
        try:
            download_video(
                video_url=args.url,
                video_id=video_id,
                output_dir=video_dir,
            )
        except RuntimeError as exc:
            print(f"✗ Video download failed: {exc}")
            raise
    else:
        print("\n[0/6] Video download: DISABLED")

    print("\n[1/6] Checking location model server...")

    session = requests.Session()
    server_info = check_model_server(session)

    print(
        "✓ Model server: "
        f"{server_info.get('model')} "
        f"({server_info.get('device')})"
    )

    print("\n[2/6] Opening TikTok...")
    print(f"Video ID: {video_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1280,
                "height": 900,
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        try:
            page.goto(
                args.url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            print("✓ TikTok page loaded")
            page.wait_for_timeout(3000)

            # ------------------------------------
            # VIDEO + PLACE
            # ------------------------------------

            print(
                "\n[3/6] Extracting video & place information..."
            )

            description = get_description(page)

            if description:
                print(
                    "✓ Description: "
                    f"{description[:100]}..."
                )
            else:
                print(
                    "✗ Description not found"
                )

            video_poi = get_video_poi(page)
            raw_places = get_places(page)

            # Fallback if POI exists in universal data but DOM link is absent.
            if not raw_places and video_poi:
                poi_id = str(
                    video_poi.get("id") or ""
                )
                poi_name = clean_text(
                    video_poi.get("name") or ""
                )

                if poi_id:
                    slug = re.sub(
                        r"[^a-zA-Z0-9]+",
                        "-",
                        poi_name,
                    ).strip("-")

                    poi_url = (
                        f"https://www.tiktok.com/place/"
                        f"{slug}-{poi_id}"
                        if slug
                        else (
                            "https://www.tiktok.com/place/"
                            f"{poi_id}"
                        )
                    )

                    raw_places.append({
                        "name": poi_name,
                        "url": poi_url,
                    })

            print(
                f"✓ Places found: {len(raw_places)}"
            )

            detailed_places = []

            for place_item in raw_places:
                place_details = get_place_details(
                    context,
                    place_item["url"],
                    known_poi=video_poi,
                )

                city, country = parse_address_components(
                    place_details.get("address")
                )

                area = place_details.get("area")

                print("  → Geocoding location...")

                geocoding_result = geocode_place(
                    name=place_details.get("name"),
                    address=place_details.get("address"),
                    area=area,
                    city=city,
                    country=country,
                )

                place_details["geocoding"] = geocoding_result
                detailed_places.append(place_details)

                print(
                    f"  📍 Name: {place_details['name']}"
                )

                if place_details.get("address"):
                    print(
                        f"     Address: {place_details['address']}"
                    )

                if (
                    geocoding_result.get("latitude")
                    is not None
                ):
                    print(
                        "     🗺 Coordinates: "
                        f"{geocoding_result['latitude']}, "
                        f"{geocoding_result['longitude']}"
                    )

            # ------------------------------------
            # COMMENTS - STREAMING PAGINATION
            # ------------------------------------

            print("\n[4/6] Getting comments...")
            print(
                f"✓ Streaming mode: lấy {COMMENT_BATCH_SIZE} comment "
                "→ xử lý ngay → chưa đủ địa chỉ mới lấy batch tiếp"
            )

            analyzed_threads = []
            seen_comment_ids = set()
            seen_address_texts = set()
            address_count = 0

            cursor = 0
            has_more = True
            total_retrieved = 0
            batch_num = 0

            while has_more and address_count < MAX_ADDRESSES:
                batch_num += 1

                comments_batch, next_cursor, has_more = get_comments_batch(
                    page,
                    video_id,
                    cursor=cursor,
                    seen_ids=seen_comment_ids,
                )

                if not comments_batch:
                    print("  ℹ Batch không có comment mới.")

                    if next_cursor == cursor:
                        break

                    cursor = next_cursor
                    time.sleep(0.5)
                    continue

                total_retrieved += len(comments_batch)

                print(
                    f"  ✓ Batch {batch_num}: {len(comments_batch)} comment "
                    f"(đã lấy tổng {total_retrieved})"
                )

                # Không sort toàn bộ comments: xử lý ngay batch vừa tải.
                batch_threads, address_count, seen_address_texts = (
                    analyze_comments_with_model(
                        page=page,
                        video_id=video_id,
                        comments=comments_batch,
                        session=session,
                        start_index=total_retrieved - len(comments_batch) + 1,
                        address_count=address_count,
                        seen_address_texts=seen_address_texts,
                    )
                )

                analyzed_threads.extend(batch_threads)

                if address_count >= MAX_ADDRESSES:
                    print(
                        f"\n  ✅ Đủ {MAX_ADDRESSES} địa chỉ → "
                        "không tải thêm comment."
                    )
                    break

                if next_cursor == cursor:
                    print("  ⚠ TikTok cursor không thay đổi. Dừng pagination.")
                    break

                cursor = next_cursor
                time.sleep(0.5)

            if total_retrieved == 0:
                print("ℹ TikTok returned 0 comments.")
            else:
                print(
                    f"✓ Streaming finished: processed {total_retrieved} comments, "
                    f"found {address_count}/{MAX_ADDRESSES} address candidate(s)."
                )

            # ------------------------------------
            # SAVE
            # ------------------------------------

            print("\n[5/6] Saving results...")

            (
                txt_path,
                json_path,
                address_comment_count,
                location_count,
            ) = save_results(
                video_id=video_id,
                video_url=args.url,
                description=description,
                places=detailed_places,
                analyzed_threads=analyzed_threads,
                output_dir=args.output,
            )

            print("\n[6/6] Done")
            print("─" * 60)
            print(f"✓ Locations          : {location_count}")
            print(f"✓ Addresses found    : {address_comment_count}")
            print(f"✓ Saved TXT          : {txt_path}")
            print(f"✓ Saved JSON         : {json_path}")
            print("─" * 60)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
