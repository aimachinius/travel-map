from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
import torch
import uvicorn


MODEL_NAME = "intfloat/multilingual-e5-small"

# Ngưỡng phân loại — có thể tinh chỉnh sau khi test thực tế.
POSITIVE_THRESHOLD = 0.60
MARGIN_THRESHOLD = 0.02

POSITIVE_EXAMPLES = [

    # =========================================================
    # 1. HỎI TRỰC TIẾP ĐỊA CHỈ
    # =========================================================

    "Địa chỉ ở đâu vậy?",
    "Địa chỉ là gì vậy?",
    "Cho xin địa chỉ",
    "Cho xin địa chỉ với",
    "Cho mình xin địa chỉ",
    "Cho mình địa chỉ với",
    "Xin địa chỉ quán",
    "Xin địa chỉ với ạ",
    "Cho hỏi địa chỉ với",
    "Cho hỏi địa chỉ quán với",
    "Địa chỉ quán này ở đâu?",
    "Địa chỉ quán là gì?",
    "Mình muốn biết địa chỉ",
    "Có thể cho mình địa chỉ không?",
    "Cho xin địa chỉ cụ thể",
    "Cho xin địa chỉ chính xác",
    "Có ai biết địa chỉ không?",
    "Ai biết địa chỉ quán này không?",
    "Địa chỉ cụ thể ở đâu vậy?",

    # English
    "What is the address?",
    "What's the address?",
    "What is the exact address?",
    "What's the exact address?",
    "Can you give me the address?",
    "Can you share the address?",
    "Please share the address",
    "What is the full address?",
    "Where is the address?",
    "Where is this located?",
    "Where is this place located?",
    "Where is this restaurant located?",
    "Where is this restaurant?",

    # =========================================================
    # 2. HỎI VỊ TRÍ CỦA QUÁN / ĐỊA ĐIỂM
    # =========================================================

    "Chỗ này ở đâu?",
    "Chỗ này ở đâu vậy?",
    "Quán này ở đâu vậy?",
    "Quán này ở đâu?",
    "Nhà hàng này ở đâu vậy?",
    "Địa điểm này ở đâu?",
    "Địa điểm này nằm ở đâu?",
    "Quán nằm ở đâu vậy?",
    "Quán nằm chỗ nào vậy?",
    "Chỗ này nằm ở đâu?",
    "Nơi này ở đâu vậy?",
    "Đây là địa điểm nào?",
    "Đây là chỗ nào vậy?",
    "Bạn quay ở đâu vậy?",
    "Video này quay ở đâu vậy?",

    # English
    "Where is this?",
    "Where is this place?",
    "Where is this restaurant?",
    "Where is this located?",
    "Where was this filmed?",
    "Where did you film this?",
    "What place is this?",
    "Where can I find this place?",
    "Where can I find this restaurant?",

    # =========================================================
    # 3. HỎI QUẬN / PHƯỜNG / THÀNH PHỐ / TỈNH
    # =========================================================

    "Quận mấy vậy?",
    "Quận mấy vậy ạ?",
    "Quán này quận mấy?",
    "Chỗ này quận mấy?",
    "Ở quận nào vậy?",
    "Ở quận nào vậy bạn?",
    "Thuộc quận nào vậy?",
    "Đây là quận nào?",
    "Phường mấy vậy?",
    "Ở phường nào vậy?",
    "Thuộc phường nào?",
    "Khu vực nào vậy?",
    "Khu này ở đâu?",
    "Ở khu nào vậy?",
    "Thuộc khu nào vậy?",
    "Thành phố nào vậy?",
    "Ở thành phố nào?",
    "Tỉnh nào vậy?",
    "Ở tỉnh nào vậy?",

    # English
    "What district is this in?",
    "Which district is this in?",
    "What city is this in?",
    "What province is this in?",
    "Which area is this in?",
    "What area is this in?",

    # =========================================================
    # 4. HỎI TÊN ĐƯỜNG / SỐ NHÀ
    # =========================================================

    "Đường nào vậy?",
    "Nằm trên đường nào?",
    "Quán nằm trên đường nào?",
    "Chỗ này ở đường nào?",
    "Tên đường là gì vậy?",
    "Tên đường nào vậy?",
    "Cho xin tên đường",
    "Số nhà bao nhiêu vậy?",
    "Số mấy vậy?",
    "Địa chỉ số mấy?",
    "Nhà số bao nhiêu?",
    "Quán ở số mấy?",
    "Quán số mấy vậy?",
    "Cho xin số nhà với",

    # English
    "What street is this on?",
    "Which street is this on?",
    "What road is this on?",
    "What street is the restaurant on?",
    "What is the house number?",

    # =========================================================
    # 5. HỎI / NHẬN DIỆN TÊN ĐỊA ĐIỂM
    # =========================================================

    "Tên quán là gì vậy?",
    "Tên quán này là gì?",
    "Tên địa điểm này là gì?",
    "Địa điểm này tên gì?",
    "Cho xin tên quán",
    "Cho xin tên địa điểm",
    "Đây là quán nào vậy?",
    "Quán nào vậy?",
    "Đây là nhà hàng nào?",
    "Tên nhà hàng là gì?",

    # =========================================================
    # 6. YÊU CẦU MAP / LOCATION
    # Chỉ giữ các câu rõ ràng đang xin vị trí
    # =========================================================

    "Cho xin location",
    "Cho xin location với",
    "Cho xin map",
    "Cho xin map với",
    "Gửi mình location với",
    "Gửi mình địa điểm với",
    "Gửi mình vị trí với",
    "Cho xin vị trí",
    "Cho xin vị trí quán",
    "Pin địa điểm này được không?",
    "Can you pin this place?",
    "Can you send the location?",
    "Can you share the location?",
    "Drop the location",
    "Drop the address",

    # =========================================================
    # 7. CÂU COMMENT CHỨA THÔNG TIN ĐỊA CHỈ THỰC TẾ
    # Đây là phần rất quan trọng
    # =========================================================

    "Quán ở 86 Nguyễn Sơn",
    "Nhà em có quán ở 86 Nguyễn Sơn",
    "Ở số 15 Lê Văn Sỹ",
    "Quán ở số 32 Nguyễn Nhữ Lãm",
    "Địa chỉ là 127 Nguyễn Chế Nghĩa",
    "Địa chỉ quán là 20 Trần Hưng Đạo",
    "Quán nằm ở 86 Nguyễn Sơn",
    "Mình biết quán này ở 86 Nguyễn Sơn",
    "Quán này ở đường Nguyễn Nhữ Lãm",
    "Nằm trên đường Nguyễn Sơn",
    "Ở Phú Thọ Hòa, Tân Phú",
    "Ở Tân Phú, Hồ Chí Minh",
    "Quán ở quận Tân Phú",
    "Chỗ này ở quận 8",
    "Đây là phố ăn đêm Nguyễn Sơn",
    "Quán này nằm trong phố ăn đêm Nguyễn Sơn",

    # English
    "The address is 86 Nguyen Son",
    "It's at 32 Nguyen Nhu Lam",
    "The restaurant is on Nguyen Son Street",
    "This place is in Tan Phu",
    "It's in District 8, Ho Chi Minh City",

    # =========================================================
    # 8. CẤU TRÚC ĐỊA CHỈ / SỐ + ĐƯỜNG / QUẬN / PHƯỜNG
    # =========================================================

    "32 Nguyễn Nhữ Lãm, Tân Phú",
    "86 Nguyễn Sơn, Tân Phú",
    "127 Nguyễn Chế Nghĩa, Quận 8",
    "20 Trần Hưng Đạo, Quận 5",
    "15 Lê Văn Sỹ, Quận 3",
    "32 Đ. Nguyễn Nhữ Lãm, Phú Thọ Hòa",
    "86 Nguyễn Sơn, Hồ Chí Minh",
    "127 Nguyễn Chế Nghĩa, Hồ Chí Minh",
    "6RVQ+6P5, Chattogram 4206, Bangladesh",

    # =========================================================
    # 9. REPLY DẠNG TRẢ LỜI ĐỊA CHỈ (quan trọng!)
    # Người dùng trả lời câu hỏi địa chỉ bằng cách nêu địa chỉ
    # =========================================================

    "Dạ quán ở 135 Láng Hạ ạ",
    "Dạ quán ở 86 Nguyễn Sơn ạ",
    "Dạ ở 17 Thuỵ Khuê ạ",
    "Dạ ở quận 8 ạ",
    "Dạ bạn ơi quán ở 127 Nguyễn Chế Nghĩa",
    "Quán ở 135 Láng Hạ bạn nhé",
    "Ở 135 Láng Hạ ạ",
    "Ở 17 Thuỵ Khuê nha bạn",
    "Bạn ơi quán ở 86 Nguyễn Sơn",
    "Mình trả lời nha: quán ở 135 Láng Hạ",
    "Quán ở Láng Hạ, Đống Đa, Hà Nội",
    "135 Láng Hạ, Đống Đa, Hà Nội",
    "Quán ở 135 Láng Hạ, Đống Đa nhé",
    "Chỗ đó ở 17 Thuỵ Khuê, Tây Hồ đó bạn",
    "Quán nằm ở 135 Láng Hạ nè",
    "Địa chỉ nè: 135 Láng Hạ, Đống Đa",
    "Đây nè: 135 Láng Hạ, Đống Đa, Hà Nội",

    # =========================================================
    # 10. ĐỊA CHỈ KHÔNG CÓ DẤU PHẨY + GHI CHÚ NGOẶC
    # Dạng: "số đường khu vực ( ghi chú thêm )"
    # =========================================================

    "95 hồ ngọc lân kinh bắc ( cuối video đó ạ )",
    "95 hồ ngọc lân kinh bắc",
    "17 thuỵ khuê ( cổng trường nha )",
    "17 thuỵ khuê tây hồ ( cạnh trường chu văn an )",
    "86 nguyễn sơn tân phú ( gần chợ đó )",
    "135 láng hạ đống đa ( bạn ghé thử nha )",
    "127 nguyễn chế nghĩa quận 8 ( mình hay ăn ở đây )",
    "32 nguyễn nhữ lãm phú thọ hoà ( trong phố ăn đêm )",
    "Số 95 hồ ngọc lân ( bạn vào cuối vid xem )",
    "95 Hồ Ngọc Lân Kinh Bắc ( gần đó thôi )",
    "86 Nguyễn Sơn ( quán ngay đầu hẻm )",
    "17 Thuỵ Khuê ( trước cổng trường )",

]

NEGATIVE_EXAMPLES = [

    # =========================================================
    # 1. ĐỒ ĂN / CẢM NHẬN
    # =========================================================

    "Đồ ăn nhìn ngon quá",
    "Trông ngon quá",
    "Ngon quá trời",
    "Ngon quá",
    "Nhìn ngon vậy",
    "Nhìn hấp dẫn ghê",
    "Chỗ này ngon lắm",
    "Ăn ngon quá",
    "Bún mắm ngon lắm",
    "Món này ngon quá",
    "Thèm quá",
    "Nhìn thèm quá",
    "Mình cũng muốn ăn",
    "Mình thích ăn bún mắm",
    "No cành hông",
    "Ăn xong 5 tô no luôn",
    "Mình ăn 5 tô luôn",
    "Tui ăn 6 tô luôn",
    "Chê nha",
    "Không ngon",
    "Hơi đắt nhỉ",
    "Giá cả hợp lý",

    # =========================================================
    # 2. GIÁ / GIỜ / MENU
    # =========================================================

    "Bao nhiêu tiền vậy?",
    "Món này giá bao nhiêu?",
    "Giá bao nhiêu?",
    "Bao nhiêu một tô?",
    "Có mắc không?",
    "Có đắt không?",
    "Mở cửa mấy giờ?",
    "Bán tới mấy giờ?",
    "Bán từ mấy giờ?",
    "Đóng cửa mấy giờ?",
    "Mấy giờ mở cửa vậy?",
    "Menu có những món gì?",
    "Có menu không?",

    # =========================================================
    # 3. CÔNG THỨC / CÁCH NẤU
    # =========================================================

    "Công thức món này là gì?",
    "Cho xin công thức",
    "Cách làm món này thế nào?",
    "Nấu món này như thế nào?",
    "Làm sao để nấu món này?",
    "What is the recipe?",
    "Can you share the recipe?",

    # =========================================================
    # 4. ĐỒ ĂN / GIAO HÀNG / ORDER
    # =========================================================

    "Có giao hàng không?",
    "Order online được không?",
    "Có ship không?",
    "Có bán online không?",
    "Can I order this online?",
    "Do you deliver?",
    "Can I order online?",

    # =========================================================
    # 5. NGUYÊN LIỆU / VỊ / ĂN ĐƯỢC KHÔNG
    # =========================================================

    "Có cay không?",
    "Món này cay không?",
    "Có ăn chay được không?",
    "Ăn chay được không?",
    "Dễ ăn không?",
    "Có ngon không?",
    "Ăn được không bạn?",
    "What does it taste like?",
    "Is this spicy?",
    "Is this vegetarian?",

    # =========================================================
    # 6. COMMENT SOCIAL / TAG / CẢM XÚC
    # =========================================================

    "First comment",
    "First",
    "Ai tag bạn tui với",
    "Kêu bạn đi ăn cùng",
    "@Nicky",
    "@Hyen",
    "@Mít Tờ Danh",
    "Kìa má",
    "Chắc chưa",
    "Thiệt hong",
    "Thiệt ko",
    "Good",
    "Amazing",
    "Love this video",
    "This looks delicious",
    "Amazing food",
    "The editing is amazing",
    "So good",
    "😂😂😂",
    "🤣🤣🤣",
    "🥰🥰🥰",

    # =========================================================
    # 7. NHỮNG CÂU CÓ TỪ "CHỖ / QUÁN" NHƯNG KHÔNG HỎI ĐỊA CHỈ
    # =========================================================

    "Chỗ này ngon lắm",
    "Chỗ này khỏi chê",
    "Quán ruột của mình",
    "Quán này ngon",
    "Quán này đông lắm",
    "Quán làm lâu lắm",
    "Mình hay ăn quán này",
    "Tui thích ăn ở đây",
    "Đã ăn ở đây rồi",
    "Mình ăn chỗ này rồi",

]


class ClassifyRequest(BaseModel):
    text: str


app = FastAPI(
    title="Location Comment Filter",
    version="1.0.0",
)


device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading model: {MODEL_NAME}")
print(f"Device: {device}")

model = SentenceTransformer(
    MODEL_NAME,
    device=device,
)

# E5 được dùng theo kiểu query -> passage.
positive_vectors = model.encode(
    [f"passage: {x}" for x in POSITIVE_EXAMPLES],
    normalize_embeddings=True,
    convert_to_numpy=True,
)

negative_vectors = model.encode(
    [f"passage: {x}" for x in NEGATIVE_EXAMPLES],
    normalize_embeddings=True,
    convert_to_numpy=True,
)

print("Model loaded.")


# ============================================================
# CLASSIFIER 2: PROVIDES ADDRESS vs ASKS FOR ADDRESS
# ============================================================

ADDRESS_PROVIDER_EXAMPLES = [
    # --- Trả lời địa chỉ cụ thể ---
    "ở 17 Nguyễn Văn Linh nha mng",
    "17 Thuỵ Khuê nhé ạ",
    "Quán ở 86 Nguyễn Sơn",
    "Địa chỉ là 127 Nguyễn Chế Nghĩa",
    "Số 32 Nguyễn Nhữ Lãm, Tân Phú",
    "Ở số 15 Lê Văn Sỹ quận 3",
    "Quán nằm ở 86 Nguyễn Sơn quận 1",
    "Địa chỉ quán là 20 Trần Hưng Đạo quận 5",
    "17 Thuỵ Khuê nhé ạ, quán ngay sát cổng trường",
    "cnay là địa chỉ của trường luôn nma quán ngay sát cổng ạ",
    "Mình biết quán này, ở 86 nguyễn sơn đó",
    "Quán ruột của mình ở 127 Nguyễn Chế Nghĩa",
    "Đây là phố ăn đêm Nguyễn Sơn, quận Tân Phú",
    "Ở Phú Thọ Hòa, Tân Phú nha",
    "Chỗ này ở quận 8, Hồ Chí Minh",
    "Nằm trên đường Nguyễn Nhữ Lãm",
    "Quán ở phố ăn đêm Nguyễn Sơn",
    "Ở trong khu chợ Tân Phú",
    "Gần trường Chu Văn An, 17 Thuỵ Khuê",
    "Nhà em có quán bún bò ở 86 Nguyễn Sơn",
    "Mình ghé quán ở 127 Nguyễn Chế Nghĩa quận 8 nhen",
    # --- Dạng reply trả lời địa chỉ ---
    "Dạ quán ở 135 Láng Hạ ạ",
    "Dạ quán ở 86 Nguyễn Sơn ạ",
    "Dạ ở 17 Thuỵ Khuê ạ",
    "Dạ bạn ơi quán ở 127 Nguyễn Chế Nghĩa",
    "Quán ở 135 Láng Hạ bạn nhé",
    "Ở 135 Láng Hạ ạ",
    "Ở 17 Thuỵ Khuê nha bạn",
    "Bạn ơi quán ở 86 Nguyễn Sơn",
    "135 Láng Hạ, Đống Đa, Hà Nội",
    "Quán ở 135 Láng Hạ, Đống Đa nhé",
    "Chỗ đó ở 17 Thuỵ Khuê, Tây Hồ đó bạn",
    "Địa chỉ nè: 135 Láng Hạ, Đống Đa",
    "Đây nè: 135 Láng Hạ, Đống Đa, Hà Nội",
    # --- Địa chỉ không dấu phẩy + ghi chú ngoặc ---
    "95 hồ ngọc lân kinh bắc ( cuối video đó ạ )",
    "95 hồ ngọc lân kinh bắc",
    "17 thuỵ khuê ( cổng trường nha )",
    "17 thuỵ khuê tây hồ ( cạnh trường chu văn an )",
    "86 nguyễn sơn tân phú ( gần chợ đó )",
    "135 láng hạ đống đa ( bạn ghé thử nha )",
    "Số 95 hồ ngọc lân ( bạn vào cuối vid xem )",
    "95 Hồ Ngọc Lân Kinh Bắc ( gần đó thôi )",
    "86 Nguyễn Sơn ( quán ngay đầu hẻm )",
    "17 Thuỵ Khuê ( trước cổng trường )",
    # English
    "The address is 86 Nguyen Son",
    "It's at 17 Thuy Khue",
    "The restaurant is on Nguyen Son Street",
    "This place is in District 8, Ho Chi Minh City",
    "Located at 32 Nguyen Nhu Lam, Tan Phu",
    "It's near Chu Van An school, 17 Thuy Khue",
]


ADDRESS_ASKER_EXAMPLES = [
    # --- Hỏi địa chỉ ---
    "Địa chỉ ở đâu vậy?",
    "Cho xin địa chỉ với",
    "Chỗ này ở đâu vậy?",
    "quận mấy vậy?",
    "Ở đâu vậy bạn?",
    "Cho xin location với",
    "Tên quán là gì?",
    "Quán nào vậy?",
    "Đường nào vậy?",
    "Số nhà bao nhiêu?",
    "Mình muốn biết địa chỉ",
    "Cho hỏi địa chỉ với ạ",
    "Ai biết địa chỉ không?",
    "Địa chỉ cụ thể ở đâu?",
    "Ko ghim địa chỉ là tội ác",
    "Vẫn không biết ở đâu",
    "Không biết quán ở đâu",
    "Nghe hết video vẫn không biết ở đâu",
    "Ko để địa chỉ à",
    "Chỗ nào ấy",
    # English
    "Where is this place?",
    "What is the address?",
    "Where is this located?",
    "Can you share the address?",
    "Which district is this?",
    "What street is this on?",
    "Drop the location",
    "Where did you film this?",
]

print("Encoding address type classifier...")
provider_vectors = model.encode(
    [f"passage: {x}" for x in ADDRESS_PROVIDER_EXAMPLES],
    normalize_embeddings=True,
    convert_to_numpy=True,
)

asker_vectors = model.encode(
    [f"passage: {x}" for x in ADDRESS_ASKER_EXAMPLES],
    normalize_embeddings=True,
    convert_to_numpy=True,
)
print("Address type classifier ready.")


def classify_address_type(text: str):
    """
    Phân loại comment location-related thành:
      PROVIDES  — comment chứa/cung cấp thông tin địa chỉ thực tế
      ASKS      — comment đang hỏi địa chỉ
      UNCLEAR   — không rõ ràng
    """
    text = (text or "").strip()
    if not text:
        return {"address_type": "UNCLEAR", "provider_score": 0.0, "asker_score": 0.0}

    vector = model.encode(
        [f"query: {text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]

    prov_sims = provider_vectors @ vector
    ask_sims = asker_vectors @ vector

    k = min(5, len(prov_sims))
    prov_score = float(np.mean(np.sort(prov_sims)[-k:]))
    ask_score = float(np.mean(np.sort(ask_sims)[-k:]))

    margin = prov_score - ask_score
    if margin > 0.015:
        address_type = "PROVIDES"
    elif margin < -0.015:
        address_type = "ASKS"
    else:
        address_type = "UNCLEAR"

    return {
        "address_type": address_type,
        "provider_score": round(prov_score, 4),
        "asker_score": round(ask_score, 4),
    }


def classify_text(text: str):
    text = (text or "").strip()

    if not text:
        raise ValueError("text is empty")

    vector = model.encode(
        [f"query: {text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]

    positive_similarities = positive_vectors @ vector
    negative_similarities = negative_vectors @ vector

    # Lấy top-5 gần nhất thay vì chỉ lấy 1 ví dụ, giảm nhiễu từ 1 example.
    pos_top = np.sort(positive_similarities)[-5:]
    neg_top = np.sort(negative_similarities)[-5:]

    positive_score = float(np.mean(pos_top))
    negative_score = float(np.mean(neg_top))
    margin = positive_score - negative_score

    related = (
        positive_score >= POSITIVE_THRESHOLD
        and margin >= MARGIN_THRESHOLD
    )

    return {
        "related": related,
        "label": "LOCATION_RELATED" if related else "NOT_LOCATION_RELATED",
        "positive_score": round(positive_score, 4),
        "negative_score": round(negative_score, 4),
        "margin": round(margin, 4),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": device,
    }


@app.post("/classify")
def classify(request: ClassifyRequest):
    try:
        result = classify_text(request.text)
        return {
            "text": request.text,
            **result,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@app.post("/classify_full")
def classify_full(request: ClassifyRequest):
    """
    Endpoint tổng hợp: trả về cả related + address_type trong một lần gọi.
      - related: True/False — có liên quan địa chỉ không
      - address_type: PROVIDES | ASKS | UNCLEAR | NOT_LOCATION
    """
    try:
        base = classify_text(request.text)
        result = {"text": request.text, **base}

        if base["related"]:
            type_info = classify_address_type(request.text)
            result.update(type_info)
        else:
            result["address_type"] = "NOT_LOCATION"
            result["provider_score"] = 0.0
            result["asker_score"] = 0.0

        return result
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )

