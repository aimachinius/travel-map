# ĐẶC TẢ HỆ THỐNG HOÀN CHỈNH: FOOD SPOT BACKEND (AGENT SYSTEM SPECIFICATION)

Tài liệu này là bộ đặc tả kỹ thuật chuẩn hóa (Ground Truth) hợp nhất toàn bộ kiến trúc, cơ sở dữ liệu không gian, luồng xử lý bất đồng bộ, hàng đợi ưu tiên kép và giao thức kết nối AI cho dự án **Food Spot Backend**.

---

## 1. TỔNG QUAN KIẾN TRÚC & CÔNG NGHỆ

### 1.1. Ngăn xếp công nghệ (Tech Stack)

* **Ngôn ngữ & Runtime**: Python >= 3.11, Uvicorn.


* **Framework**: FastAPI hỗ trợ đồng thời REST API và WebSocket thời gian thực.


* **Cơ sở dữ liệu & GIS**: PostgreSQL tích hợp tiện ích không gian **PostGIS**.


* **ORM & Migration**: SQLAlchemy, GeoAlchemy2 (xử lý kiểu hình học `Geometry(POINT, 4326)`), Alembic.


* **Hàng đợi & Cache**: Redis (quản lý Dual-Priority Job Queue và chống trùng lặp URL), `cachetools` (TTLCache cho vùng hành chính).

* **Async HTTP Client**: `httpx` (giao tiếp bất đồng bộ với External AI Server và ArcGIS Geocoder).

* **Cào dữ liệu (Web Scraping)**: `playwright` (`chromium-headless-shell`) phục vụ tiến trình tự động cào link video TikTok theo từ khóa.

* **Tính toán diện tích & Độ phủ hành chính**: `shapely`, `pyproj` (phép chiếu Azimuthal Equidistant `+proj=aeqd`).

* **Xác thực & Kiểm thử**: JWT Bearer Token, Passlib/Bcrypt, Pydantic v2, Pytest (`pytest-asyncio`).



### 1.2. Cấu trúc thư mục chuẩn hóa

```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # Dependency injection (DB session, JWT current user)
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py          # Đăng ký, đăng nhập, lấy thông tin tài khoản
│   │       │   ├── health.py        # Kiểm tra trạng thái hệ thống
│   │       │   ├── videos.py        # Submit URL video, tra cứu lịch sử phân tích
│   │       │   ├── places.py        # Tìm kiếm không gian PostGIS, xem video theo quán
│   │       │   ├── saved.py         # Bookmark lưu/bỏ lưu video và địa điểm
│   │       │   └── ws.py            # WebSocket endpoint nhận thông báo real-time
│   │       └── router.py            # Gom nhóm toàn bộ API routes
│   ├── core/
│   │   ├── config.py                # Biến môi trường (DB, JWT, AI URL, Redis)
│   │   ├── security.py              # Hash mật khẩu & tạo/giải mã JWT
│   │   └── websocket_manager.py     # Quản lý kết nối WebSocket theo user_id
│   ├── db/
│   │   └── session.py               # Khởi tạo kết nối PostgreSQL/PostGIS
│   ├── models/                      # SQLAlchemy & GeoAlchemy2 Models (8 bảng)
│   ├── schemas/                     # Pydantic v2 Request/Response Schemas
│   ├── services/
│   │   ├── auth_service.py          # Nghiệp vụ xác thực
│   │   ├── video_service.py         # Nghiệp vụ quản lý video
│   │   ├── analysis_service.py      # Điều phối hàng đợi & gọi External AI Server
│   │   ├── geocoding_service.py     # Chuẩn hóa địa chỉ & tọa độ qua ArcGIS Geocoder
│   │   ├── discovery_service.py     # Tự động phân giải vùng hành chính, sinh từ khóa & cào video TikTok
│   │   ├── place_service.py         # Truy vấn bán kính PostGIS & thông tin quán
│   │   └── saved_service.py         # Nghiệp vụ lưu trữ mục yêu thích
│   └── main.py                      # Entrypoint khởi chạy ứng dụng & background workers
├── alembic/                         # Quản lý lịch sử migration database
├── tests/                           # Unit test & Integration test
├── .env.example
├── alembic.ini
├── requirements.txt
└── README.md

```

---

## 2. ACTIVITY DIAGRAMS (UML) & MÔ TẢ LUỒNG HOẠT ĐỘNG

### 2.1. Liên kết tổng thể giữa các chức năng (Cross-Function Interaction)

Hệ thống vận hành xoay quanh vòng lặp làm giàu dữ liệu bản đồ tự động và phục vụ người dùng theo thời gian thực:

1. **Nguồn thu thập dữ liệu (Ingestion)**: Hệ thống nhận link video từ hai nguồn: người dùng chủ động gửi link (`USER_SUBMIT` - Ưu tiên 1) và tiến trình tự động quét từ vị trí ghim trên bản đồ (`SYSTEM_DISCOVERY` - Ưu tiên 2).


2. **Xử lý & Chuẩn hóa (Processing & Geocoding)**: Worker ưu tiên xử lý yêu cầu của người dùng trước, gọi External AI Server để trích xuất tên quán/địa chỉ, sau đó gọi `ArcGISGeocoder` để chuyển địa chỉ văn bản thành tọa độ không gian PostGIS (`POINT`).


3. **Phân phối & Tương tác (Delivery & Engagement)**: Kết quả hoàn tất được đẩy tức thời qua WebSocket về cho người dùng, đồng thời làm giàu trực tiếp vào bảng `places` và `video_place_matches`. Khi người dùng quét bản đồ theo bán kính hoặc bấm vào một quán ăn, dữ liệu từ cả hai nguồn sẽ được truy vấn qua PostGIS để đề xuất video và cho phép lưu vào danh sách yêu thích.



---

### 2.2. Luồng 1: Người dùng gửi link video phân tích (User On-Demand Submission)

```mermaid
flowchart TD
    Start([Bắt đầu: User gửi POST /api/v1/videos/submit]) --> AuthCheck{JWT Token hợp lệ &<br/>User đang active?}
    AuthCheck -- Không --> Err401([Trả về 401/403 Unauthorized])
    AuthCheck -- Có --> ValidateURL{URL thuộc TikTok<br/>hoặc YouTube?}
    
    ValidateURL -- Không --> Err422([Trả về 422 Invalid URL])
    ValidateURL -- Có --> ExtractID[Trích xuất platform & platform_video_id]
    
    ExtractID --> CheckVideoDB{Video đã tồn tại<br/>trong bảng videos?}
    CheckVideoDB -- Chưa có --> CreateVideo[Tạo bản ghi mới trong bảng videos]
    CheckVideoDB -- Đã có --> GetVideo[Lấy bản ghi video hiện có]
    
    CreateVideo --> CheckCompleted{Đã có kết quả phân tích<br/>COMPLETED trước đó?}
    GetVideo --> CheckCompleted
    
    CheckCompleted -- Đã có & Không yêu cầu chạy lại --> ReturnCached([Trả về ngay dữ liệu quán ăn đã khớp])
    CheckCompleted -- Chưa có --> CreateRun[Tạo bản ghi analysis_runs:<br/>status = PENDING<br/>trigger_source = USER_SUBMIT<br/>priority = 1]
    
    CreateRun --> PushHighQueue[Đẩy task vào Redis Queue:<br/>queue:high_priority]
    PushHighQueue --> Return202([Trả về 202 Accepted:<br/>video_id, analysis_run_id, status=PENDING])
    Return202 --> ListenWS([Client lắng nghe sự kiện qua WebSocket /api/v1/ws])

```

* **Các bước xử lý & Điều kiện rẽ nhánh**:
1. **Kiểm tra xác thực và định dạng**: Xác thực JWT của người dùng đang hoạt động (`is_active == True`), sau đó kiểm tra mẫu URL hợp lệ của TikTok hoặc YouTube để bóc tách `platform_video_id`.


2. **Rẽ nhánh kiểm tra tồn tại Video (`Get or Create`)**:
* *Nhánh chưa tồn tại*: Lưu thông tin đường dẫn gốc (`source_url`), `platform` và `platform_video_id` vào bảng `videos`.


* *Nhánh đã tồn tại*: Lấy `video.id` sẵn có để tránh trùng lặp bản ghi. Nếu video đã có kết quả phân tích thành công, hệ thống có thể trả ngay dữ liệu địa điểm đã khớp.




3. **Khởi tạo tiến trình ưu tiên cao**: Tạo bản ghi `analysis_runs` với `status = PENDING`, `trigger_source = USER_SUBMIT`, `priority = 1`, đẩy vào `queue:high_priority` và phản hồi ngay lập tức cho Client để không làm treo giao diện.





---

### 2.3. Luồng 2: Tự động quét & cào video theo vị trí bản đồ (`SYSTEM_DISCOVERY` — Mức ưu tiên 2 / Priority 2)

Nguồn này giúp tự động làm giàu dữ liệu cho bản đồ ẩm thực tại khu vực người dùng quan tâm mà không cần người dùng phải tự tìm và gửi từng link video. Hệ thống áp dụng **Kiến trúc Đường ống Dạng dòng (Streaming Pipeline)**: Cào xong từ khóa nào là lập tức lọc trùng, lưu DB và đẩy ngay vào hàng đợi Redis để Server AI phân tích song song, không phải chờ cào xong toàn bộ từ khóa.

```mermaid
flowchart TD
    Start([Bắt đầu: User ghim/chọn tọa độ lat, lon trên Map]) --> CheckScanCache{Vùng này đang quét hoặc<br/>cách <= 1km trong 24h?<br/>bảng discovery_scans}
    
    CheckScanCache -- Đã quét / Cách <= 1km --> SkipScan([Bỏ qua quét mới - Trả kết quả sẵn có trong DB])
    CheckScanCache -- Chưa quét / Hết hạn --> SaveScanLog[Ghi nhận tọa độ & bán kính vào bảng discovery_scans]
    
    SaveScanLog --> ResolveArea[Gọi mô-đun find/area:<br/>1. resolve_current_address lat, lon<br/>2. get_district_coverage tính độ phủ Phường/Quận]
    ResolveArea --> AreaSuccess{Trích xuất được tên<br/>Phường/Quận/Thành phố?}
    
    AreaSuccess -- Không --> EndFail([Kết thúc tiến trình Discovery])
    AreaSuccess -- Có --> GenKeywords[Sinh bộ từ khóa phân tách ít trùng lặp:<br/>- 'quán ăn ở + Khu vực'<br/>- 'quán cafe ở + Khu vực'<br/>- 'ăn vặt + Khu vực']
    
    GenKeywords --> FilterKeywords[Lọc bỏ từ khóa đã dùng trong 24h qua]
    FilterKeywords --> CheckRemaining{Còn từ khóa mới<br/>cần cào không?}
    CheckRemaining -- Hết --> EndDone([Bỏ qua cào - Toàn bộ từ khóa đã cào trong 24h])
    
    CheckRemaining -- Còn --> ForEachKeyword[Vòng lặp từng từ khóa cào Streaming]
    
    subgraph StreamPipeline["Cơ chế Streaming: Cào tới đâu đẩy AI Server phân tích tới đó"]
        ForEachKeyword --> CrawlKW[Cào TikTok cho từ khóa này<br/>Playwright Headless + Session Warmup]
        CrawlKW --> LoopLinks[Duyệt danh sách link vừa cào được của từ khóa]
        LoopLinks --> CheckDuplicate{Video đã tồn tại<br/>trong DB / analysis_runs?}
        CheckDuplicate -- Đã có --> NextLink{Còn link trong từ khóa?}
        CheckDuplicate -- Chưa có --> SaveVideo[Lưu bảng videos & tạo analysis_runs<br/>status = PENDING, priority = 2]
        SaveVideo --> PushQueue[Đẩy ngay vào Redis queue:low_priority]
        PushQueue --> ParallelAI[Background Worker rút task & gửi sang Server AI phân tích song song]
        PushQueue --> NextLink
        NextLink -- Còn link --> LoopLinks
        NextLink -- Hết link --> DelayKW[Nghỉ 5s chống rate-limit TikTok]
    end
    
    DelayKW --> NextKW{Còn từ khóa<br/>tiếp theo?}
    NextKW -- Còn --> ForEachKeyword
    NextKW -- Hết --> UpdateScan[Cập nhật videos_found_count vào discovery_scans]
    UpdateScan --> EndSuccess([Hoàn tất phiên Discovery])
```

#### 2.3.1. Thời điểm kích hoạt & Cơ chế chống quét lặp

* **Sự kiện kích hoạt**: Khi người dùng ghim hoặc chọn một tọa độ `(lat, lon)` kèm bán kính `radius_m` trên bản đồ (hoặc khi gọi endpoint `GET /api/v1/places/nearby-videos`).
* **Kiểm tra vùng quét (`discovery_scans` & Khoảng cách <= 1km)**:
  * Hệ thống kiểm tra xem tọa độ mới `(lat, lon)` có nằm cách bất kỳ điểm quét nào trong vòng **24 giờ qua** một khoảng cách $\le 1000\text{m}$ ($1\text{km}$) hay không (`ST_DWithin(center_location::geography, target_point::geography, 1000)`).
  * **Nếu khoảng cách $\le 1000\text{m}$**: Coi như cùng một vùng không gian đã có dữ liệu, **bỏ qua tiến trình quét mới** và trả về ngay dữ liệu sẵn có trong DB.
  * **Nếu cách xa $> 1000\text{m}$ (hoặc chưa quét)**: Ghi nhận bản ghi vùng quét mới vào bảng `discovery_scans` và kích hoạt ngầm `DiscoveryService`.

#### 2.3.2. Quy trình thu thập video tự động (4 Bước chi tiết)

1. **Bước 1: Lấy tên vị trí & Đơn vị hành chính từ tọa độ `(lat, lon)`** *(Tham chiếu đặc tả [`referent_for_BE/area/dat_ta_tim_khu_vuc.md`](../referent_for_BE/area/dat_ta_tim_khu_vuc.md))*:
   * **Phân giải địa chỉ điểm ghim (`resolve_current_address`)**: Sử dụng cơ chế phân giải 3 lớp dự phòng (*Nominatim OSM API* $\rightarrow$ *ArcGIS World Geocoding Service* $\rightarrow$ *Photon Komoot Geocoder*) kết hợp hàm chuẩn hóa tiền tố `_normalize_prefix` để lấy tên Phường/Xã (`ward`), Quận/Huyện (`district`) và Tỉnh/Thành phố (`city`) (ví dụ: `"Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng"`).
   * **Tính độ phủ các khu vực lân cận trong bán kính (`get_district_coverage` / `DistrictCoverageService`)**: Chiếu tọa độ sang hệ phẳng cục bộ Azimuthal Equidistant (`+proj=aeqd`), dựng vùng đệm hình tròn bán kính `radius_m` và tính tỷ lệ diện tích giao cắt (`percentage` %) với các đa giác hành chính OpenStreetMap (`admin_level="6"` hoặc `"8"`) để trích xuất danh sách các Phường/Quận thực tế nằm trong vùng bán kính (ví dụ: *Phường Hòa Khánh Nam, Phường Hòa Minh, Quận Liên Chiểu tại Đà Nẵng*).
   * **Lưu đệm (Cache)**: Tận dụng `TTLCache` (`.cache_area.json` với khóa `addr:{lat}:{lon}` và `area:{lat}:{lon}:{radius_m}:{admin_level}`, TTL 24 giờ) để giảm tải truy vấn ra máy chủ bản đồ.

2. **Bước 2: Tự động sinh bộ từ khóa ẩm thực phân tách & Lọc từ khóa đã dùng trong 24h**:
   * **Quy chuẩn nguồn địa danh**: **CHỈ lấy tên từ cấp đơn vị hành chính cấp Xã/Phường (`ward`) trở lên (`district`, `city`)**. Tuyệt đối không dùng tên POI (trường học, quán xá, địa điểm công cộng):
     * Cấp Xã / Phường: Ví dụ `"Hòa Khánh Nam, Đà Nẵng"`, `"Hòa Minh, Đà Nẵng"`.
     * Cấp Quận / Huyện: Ví dụ `"Liên Chiểu, Đà Nẵng"`.
     * Bảo vệ các đơn vị dạng số: Giữ nguyên `"Quận 1"`, `"Quận 3"`, `"Phường 10"` tránh rút gọn thành số đơn lẻ.
   * **Phân tách 3 danh mục rõ rệt**:
     * **Nhóm món ăn / bữa chính**: `quán ăn ở [Tên Phường/Quận, Tên TP]` hoặc `ăn gì ở [Tên Phường/Quận, Tên TP]`.
     * **Nhóm đồ uống / cafe**: `quán cafe ở [Tên Phường/Quận, Tên TP]`.
     * **Nhóm ăn vặt**: `ăn vặt [Tên Phường/Quận, Tên TP]`.
   * **Cơ chế lọc từ khóa đã cào trong 24 giờ qua**:
     * Truy vấn danh sách `keywords_generated` từ bảng `discovery_scans` được thực hiện trong vòng 24 giờ qua.
     * So sánh và loại bỏ toàn bộ các từ khóa đã từng được dùng để cào trong 24 giờ qua (không phân biệt hoa thường).
     * **Nếu toàn bộ từ khóa đều đã được cào trong 24h**: Bỏ qua tiến trình cào, trả về kết quả sẵn có trong DB.
     * **Nếu còn từ khóa mới**: Chỉ cào các từ khóa mới này, đồng thời lưu danh sách từ khóa mới vào cột `keywords_generated` (JSONB) của bảng `discovery_scans`.

3. **Bước 3: Cào link video TikTok & Nạp dòng tức thì (Streaming Ingestion Pipeline)** *(Tham chiếu đặc tả [`referent_for_BE/cao_link/dat_ta_cao_link.md`](../referent_for_BE/cao_link/dat_ta_cao_link.md))*:
   * Thay vì cơ chế Gom Lô (chờ cào xong toàn bộ 6 từ khóa mới lưu), hệ thống triển khai theo mô hình **Streaming Ingestion**: Cào xong từ khóa nào là lập tức xử lý và đẩy sang AI Server ngay từ khóa đó.
   * Duyệt qua từng từ khóa hợp lệ và gọi `crawl_tiktok_links_async(query=keyword, scroll_count=3, headless=True)`:
     * **Khởi tạo & Anti-Bot**: Viewport 1920x1080, `locale="vi-VN"`, ẩn cờ `navigator.webdriver`, thực hiện Session Warmup truy cập `https://www.tiktok.com/explore` trong 2.5s lấy cookie trước khi tìm kiếm.
     * **Cuộn trang & Trích xuất**: Tự động đóng modal đăng nhập, xử lý nút "Thử lại", cuộn trang 3 lần (cách nhau 2.5s) và trích xuất `a[href*='/video/']`.
     * **Làm sạch URL**: Cắt bỏ tracking query sau dấu `?` (`split('?')[0]`) để chuẩn hóa về dạng `https://www.tiktok.com/@<author>/video/<id>`.
     * **Chống khóa IP (Rate Limit)**: Duy trì độ trễ **5 giây** giữa các lần cào từ khóa kế tiếp.

4. **Bước 4: Khử trùng lặp, Lưu DB & Đẩy ngay sang Server AI theo thời gian thực**:
   * Ngay sau khi cào xong 1 từ khóa, duyệt ngay danh sách URL của từ khóa đó:
     * Kiểm tra `platform_video_id` trong bảng `videos` và `analysis_runs` (`PENDING`, `PROCESSING`, `COMPLETED`).
     * **Nếu chưa tồn tại**:
       1. Lưu bản ghi vào bảng `videos` (`platform='tiktok'`, `platform_video_id`, `video_url`).
       2. Tạo bản ghi `analysis_runs` (`user_id=NULL`, `status='PENDING'`, `trigger_source='SYSTEM_DISCOVERY'`, `priority=2`).
       3. **Đẩy task ngay lập tức vào Redis `queue:low_priority`**.
       4. `background_queue_worker` ngay lập tức rút task và gửi HTTP POST sang Server AI (`AI_SERVER_EXTRACT_URL`) để bóc tách địa điểm ẩm thực song song.
   * **Hiệu quả**: Server AI phân tích song song ngay từ phút đầu tiên, các quán ăn tìm thấy sẽ xuất hiện dần trên bản đồ theo thời gian thực (real-time map enrichment) mà không cần chờ cào xong toàn bộ các từ khóa.
   * Kết thúc toàn bộ các từ khóa, cập nhật tổng số lượng video tìm thấy lũy kế vào cột `videos_found_count` của bảng `discovery_scans`.





---

### 2.4. Luồng 3: Worker điều phối Hàng đợi kép, Gọi AI Server & Chuẩn hóa tọa độ ArcGIS

```mermaid
flowchart TD
    Start([Worker lắng nghe Redis Queue]) --> CheckHigh{queue:high_priority<br/>có task không?}
    
    CheckHigh -- Có --> PopHigh[Lấy task từ queue:high_priority<br/>Yêu cầu của User]
    CheckHigh -- Rỗng --> CheckLow{queue:low_priority<br/>có task không?}
    
    CheckLow -- Rỗng --> Wait[Chờ chu kỳ tiếp theo] --> CheckHigh
    CheckLow -- Có --> PopLow[Lấy task từ queue:low_priority<br/>Video tự động cào]
    
    PopHigh --> StartAnalysis[Gọi start_analysis:<br/>Đổi status -> PROCESSING]
    PopLow --> StartAnalysis
    
    StartAnalysis --> NotifyProc{trigger_source ==<br/>USER_SUBMIT?}
    NotifyProc -- Có --> WSProcessing[Gửi WebSocket: status = PROCESSING]
    NotifyProc -- Không --> CallAIServer
    WSProcessing --> CallAIServer[Gọi POST AI_SERVER_EXTRACT_URL<br/>qua httpx.AsyncClient timeout=180s]
    
    CallAIServer --> CheckAIResp{HTTP 200 &<br/>status == SUCCESS?}
    
    CheckAIResp -- Lỗi / Timeout --> FailAnalysis[Gọi fail_analysis:<br/>status = FAILED, lưu error_message]
    FailAnalysis --> NotifyFail{trigger_source ==<br/>USER_SUBMIT?}
    NotifyFail -- Có --> WSFail[Gửi WebSocket: status = FAILED] --> EndTask([Kết thúc Task])
    NotifyFail -- Không --> EndTask
    
    CheckAIResp -- Thành công --> UpdateVideo[Cập nhật bảng videos:<br/>duration, file_size, transcript_text]
    UpdateVideo --> CheckRest{AI trích xuất được<br/>data.restaurant?}
    
    CheckRest -- Không có quán --> CompleteNoPlace[Cập nhật analysis_runs:<br/>status = COMPLETED] --> NotifyComp
    CheckRest -- Có thông tin quán --> NormalizeAddr[ArcGISGeocoder.generate_sub_queries:<br/>Chuẩn hóa viết tắt, tách số nhà & tên đường]
    
    NormalizeAddr --> CallArcGIS[Gọi ArcGIS findAddressCandidates<br/>countryCode = VNM]
    CallArcGIS --> CheckGeocode{Khớp số nhà hoặc<br/>Score >= 80?}
    
    CheckGeocode -- Có tọa độ --> CreatePoint[Tạo PostGIS Point SRID 4326:<br/>POINT lon lat & lưu địa chỉ chuẩn hóa]
    CheckGeocode -- Không tìm thấy --> NullPoint[Ghi log cảnh báo,<br/>lưu address gốc, location = NULL]
    
    CreatePoint --> UpsertPlace[Lưu/Cập nhật bảng places &<br/>Tạo bản ghi video_place_matches]
    NullPoint --> UpsertPlace
    
    UpsertPlace --> CompleteRun[Gọi complete_analysis:<br/>Lưu keyframes, ocr_data, metrics<br/>Đổi status -> COMPLETED]
    CompleteRun --> NotifyComp{trigger_source ==<br/>USER_SUBMIT?}
    NotifyComp -- Có --> WSSuccess[Gửi WebSocket: status = COMPLETED<br/>kèm thông tin quán & tọa độ] --> EndTask
    NotifyComp -- Không --> EndTask

```

* **Các bước xử lý & Điều kiện rẽ nhánh**:
1. **Chiến lược ưu tiên tuyệt đối (Strict Priority Polling)**: Worker luôn kiểm tra `queue:high_priority` trước; chỉ khi hàng đợi của người dùng hoàn toàn trống thì Worker mới rút tác vụ từ `queue:low_priority`.


2. **Giao tiếp AI Server**: Chuyển trạng thái sang `PROCESSING`, gửi request bất đồng bộ sang `AI_SERVER_EXTRACT_URL`. Nếu xảy ra lỗi mạng, timeout quá 180 giây hoặc AI trả về thất bại, hệ thống gọi `fail_analysis()`, lưu `error_message` và bắn thông báo lỗi qua WebSocket.


3. **Chuẩn hóa địa chỉ & Geocoding qua ArcGIS**:
* Địa chỉ thô từ `data.restaurant.address` được tiền xử lý qua Regex (thay viết tắt `q.`, `p.`, `đ.`, `hn`, `tphcm`, tách số nhà và thêm tiền tố `Đường`) để sinh danh sách biến thể truy vấn.


* Gọi duy nhất dịch vụ **ArcGIS World Geocoder** (`countryCode=VNM`). Ưu tiên chọn ứng viên khớp chính xác số nhà (`PointAddress` / `AddNum`) hoặc có điểm tin cậy `Score >= 80`.


* Nếu tìm thấy tọa độ: Khởi tạo điểm hình học PostGIS `ST_SetSRID(ST_MakePoint(lon, lat), 4326)` lưu vào bảng `places`. Nếu không tìm thấy: Vẫn lưu tên và địa chỉ thô vào `places` với `location = None` để không làm mất dữ liệu trích xuất.







---

### 2.5. Luồng 4: Truy vấn Bán kính trên Map, Xem chi tiết Quán & Lưu Yêu thích

```mermaid
flowchart TD
    UserMap([User thao tác trên Bản đồ / Giao diện]) --> ActionType{Loại hành động?}
    
    %% Nhánh 1: Tìm video trong bán kính
    ActionType -- 1. Chọn bán kính quanh tâm --> GetNearby[GET /api/v1/places/nearby-videos<br/>lat, lon, radius_m]
    GetNearby --> PostGISQuery[Thực thi truy vấn PostGIS:<br/>ST_DWithin location, user_point, radius_m<br/>Tính khoảng cách bằng ST_Distance]
    PostGISQuery --> CheckAuth1{User đã đăng nhập?}
    CheckAuth1 -- Có --> AttachSaved1[Kiểm tra bảng saved_videos & saved_places<br/>gắn cờ is_video_saved, is_place_saved]
    CheckAuth1 -- Không --> SortDist[Sắp xếp theo distance_m tăng dần]
    AttachSaved1 --> SortDist --> ReturnNearby([Trả về danh sách Video kèm tọa độ Quán])
    
    %% Nhánh 2: Xem video tại 1 địa điểm
    ActionType -- 2. Bấm vào 1 ghim quán trên Map --> GetPlaceVideos[GET /api/v1/places/place_id/videos]
    GetPlaceVideos --> CheckPlaceExists{place_id tồn tại<br/>trong bảng places?}
    CheckPlaceExists -- Không --> Err404Place([Trả về 404 Not Found])
    CheckPlaceExists -- Có --> QueryMatches[Truy vấn video_place_matches JOIN videos<br/>Sắp xếp: confidence_status HIGH trước, created_at DESC]
    QueryMatches --> ReturnPlaceVideos([Trả về thông tin Quán & danh sách Video review])
    
    %% Nhánh 3: Lưu / Bỏ lưu yêu thích
    ActionType -- 3. Bấm Lưu / Bỏ lưu Video hoặc Quán --> AuthReq{Kiểm tra JWT Token}
    AuthReq -- Không hợp lệ --> Err401Save([Trả về 401 Unauthorized])
    AuthReq -- Hợp lệ --> CheckTarget{Đối tượng Video/Place<br/>tồn tại trong DB?}
    CheckTarget -- Không --> Err404Target([Trả về 404 Not Found])
    CheckTarget -- Có --> MethodCheck{HTTP Method?}
    MethodCheck -- POST Lưu --> UpsertSaved[Kiểm tra UniqueConstraint user_id + target_id:<br/>Chưa có -> Tạo mới 201 Created<br/>Đã có -> Giữ nguyên 200 OK Idempotent]
    MethodCheck -- DELETE Bỏ lưu --> DeleteSaved[Xóa bản ghi khớp user_id + target_id<br/>Trả về 204 No Content]
    UpsertSaved --> EndSave([Hoàn tất cập nhật Bookmark])
    DeleteSaved --> EndSave

```

---

## 3. ĐẶC TẢ CƠ SỞ DỮ LIỆU & POSTGIS SCHEMA

Migration khởi tạo của Alembic bắt buộc thực thi câu lệnh kích hoạt PostGIS đầu tiên:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

```

### Chi tiết 8 Bảng Dữ liệu

| STT | Tên bảng | Các cột chính & Kiểu dữ liệu | Ràng buộc & Chỉ mục (Constraints & Indexes) |
| --- | --- | --- | --- |
| 1 | **`users`** | `id` (PK), `email` (String), `username` (String), `hashed_password` (String), `is_active` (Boolean, Default `True`), `created_at` (DateTime)

 | Unique Index trên `email` và `username`.

 |
| 2 | **`places`** | `id` (PK), `name` (String), `address` (Text), `normalized_address` (Text, Nullable), `location` (`Geometry('POINT', srid=4326)`, Nullable), `latitude` (Float, Nullable), `longitude` (Float, Nullable), `category` (String, Nullable), `created_at` (DateTime)

 | Spatial Index (GIST) tự động trên cột `location`; Index trên `name`.

 |
| 3 | **`videos`** | `id` (PK), `platform` (String: `tiktok`/`youtube`), `platform_video_id` (String), `source_url` (Text), `title` (Text, Nullable), `duration_seconds` (Float, Nullable), `file_size_mb` (Float, Nullable), `transcript_text` (Text, Nullable), `created_at` (DateTime)

 | Unique Index trên `platform_video_id` để chống trùng lặp video.

 |
| 4 | **`video_place_matches`** | `id` (PK), `video_id` (FK -> `videos.id`), `place_id` (FK -> `places.id`), `confidence_status` (String: `HIGH`/`MEDIUM`/`LOW`), `evidence_sources` (JSONB: `["audio", "vision"]`), `matched_at` (DateTime)

 | Khóa ngoại liên kết N-N giữa `videos` và `places`; UniqueConstraint(`video_id`, `place_id`).

 |
| 5 | **`analysis_runs`** | `id` (PK), `user_id` (FK -> `users.id`, Nullable cho System Discovery), `video_id` (FK -> `videos.id`), `status` (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), `trigger_source` (`USER_SUBMIT`, `SYSTEM_DISCOVERY`), `priority` (Integer: `1` hoặc `2`), `keyframes_data` (JSONB), `ocr_data` (JSONB), `execution_metrics` (JSONB), `error_message` (Text, Nullable), `created_at`, `updated_at`

 | Index trên (`status`, `priority`, `created_at`) để truy vấn tiến trình nhanh.

 |
| 6 | **`saved_videos`** | `id` (PK), `user_id` (FK -> `users.id`), `video_id` (FK -> `videos.id`), `created_at` (DateTime)

 | `UniqueConstraint('user_id', 'video_id', name='uq_user_saved_video')`.

 |
| 7 | **`saved_places`** | `id` (PK), `user_id` (FK -> `users.id`), `place_id` (FK -> `places.id`), `created_at` (DateTime)

 | `UniqueConstraint('user_id', 'place_id', name='uq_user_saved_place')`.

 |
| 8 | **`discovery_scans`** | `id` (PK), `center_location` (`Geometry('POINT', srid=4326)`), `radius_m` (Float), `keywords_generated` (JSONB), `videos_found_count` (Integer), `scanned_at` (DateTime)

 | Spatial Index trên `center_location` để kiểm tra vùng đã quét.

 |

---

## 4. ĐẶC TẢ TÍCH HỢP DỊCH VỤ NGOÀI (EXTERNAL AI & ARCGIS)

### 4.1. Giao thức kết nối External AI Server (`app/services/analysis_service.py`)

* **Cấu hình (`app/core/config.py`)**:
* `AI_SERVER_EXTRACT_URL = "[https://excess-dom-upper-ranch.trycloudflare.com/api/v1/extract](https://excess-dom-upper-ranch.trycloudflare.com/api/v1/extract)"`.


* `AI_REQUEST_TIMEOUT = 180` (giây).




* **Request Payload**: `POST` với JSON body `{"url": "<source_url>"}`.


* **Ánh xạ dữ liệu Response từ AI vào Database**:
* `data.video` (`duration_seconds`, `file_size_mb`) & `data.transcript.text` $\rightarrow$ Cập nhật vào bảng `videos`.


* `data.restaurant` (`name`, `address`, `confidence_status`, `evidence_sources`) $\rightarrow$ Chuyển qua `ArcGISGeocoder` để lấy tọa độ, lưu vào bảng `places` và `video_place_matches`.


* `data.keyframes`, `data.frames_ocr_details`, `data.execution_metrics` $\rightarrow$ Lưu vào các cột JSONB tương ứng của bảng `analysis_runs`.





### 4.2. Dịch vụ Chuẩn hóa & Định vị Tọa độ (`app/services/geocoding_service.py`)

Hệ thống phân tách rõ hai cơ chế định vị địa lý:
* **Định vị quán ăn từ địa chỉ AI trích xuất (Forward Geocoding)**: Sử dụng duy nhất **ArcGIS World Geocoding Service** nhằm tối ưu độ chính xác số nhà (`PointAddress`) tại Việt Nam.
* **Phân giải địa chỉ khu vực ghim trên Map (Discovery Reverse Resolution)**: Sử dụng chuỗi dự phòng 3 lớp (*Nominatim OSM* $\rightarrow$ *ArcGIS Geocoder* $\rightarrow$ *Photon Komoot*) kết hợp tính toán độ phủ hành chính Shapely (xem chi tiết tại Mục 2.3).

1. **Tiền xử lý chuỗi địa chỉ quán ăn (`generate_sub_queries`)**:
* Chuyển các dấu gạch ngang `" - "` thành dấu phẩy `", "`.
* Áp dụng từ điển Regex mở rộng viết tắt tiếng Việt (`tp.`, `tphcm`, `hn`, `q.`, `p.`, `tx.`, `tt.`, `đ.`, `ng.`, `h.`) và tên quận hay viết tắt (`phú` $\rightarrow$ `Phú Nhuận`, `bình thạnh`, `gò vấp`...).
* Bóc tách số nhà ở đầu chuỗi và tự động chèn tiền tố `"Đường"` kèm dấu phẩy ngăn cách tên quận/thành phố để tối ưu hóa độ chính xác `PointAddress` của ArcGIS.

2. **Forward Geocoding địa điểm (`geocode_address`)**:
* Gọi `GET https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates` với `countryCode=VNM`, `maxLocations=5`.
* **Luật chọn ứng viên**: Ưu tiên số 1 là ứng viên có `AddNum` hoặc `Match_addr`/`LongLabel` chứa chính xác số nhà mục tiêu; ưu tiên số 2 là ứng viên đứng đầu có `score >= 80`.
* Trả về bộ 3 giá trị `(latitude, longitude, normalized_address)` để tạo `WKTElement(f"POINT({lon} {lat})", srid=4326)`.

3. **Reverse Geocoding điểm đơn (`reverse_geocode`)**:
* Gọi `GET https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode` với `location=f"{lon},{lat}"` và `langCode="vi"` khi cần tra cứu nhanh tên đường/địa danh lân cận của một điểm tọa độ đơn lẻ.





---

## 5. ĐẶC TẢ REAL-TIME WEBSOCKET (`app/core/websocket_manager.py`)

* **Endpoint**: `WS /api/v1/ws?token=<JWT_ACCESS_TOKEN>`.


* **Cơ chế quản lý**: Lớp `ConnectionManager` duy trì từ điển `active_connections: dict[int, list[WebSocket]]` ánh xạ từ `user_id` sang danh sách các thiết bị đang mở kết nối của người dùng đó.


* **Payload sự kiện chuẩn gửi về Client**:

```json
{
  "event": "ANALYSIS_UPDATED",
  "data": {
    "analysis_run_id": 45,
    "video_id": 12,
    "status": "COMPLETED",
    "restaurant": {
      "id": 8,
      "name": "GIEF HO",
      "address": "34 Ngọc Khánh, Ba Đình, Hà Nội",
      "latitude": 21.0285,
      "longitude": 105.8154
    },
    "error_message": null
  }
}

```

---

## 6. ĐẶC TẢ CHI TIẾT CÁC NHÓM REST API ENDPOINTS

### 6.1. Nhóm Authentication (`/api/v1/auth`)

* `POST /api/v1/auth/register`: Đăng ký tài khoản mới, băm mật khẩu bằng Bcrypt.


* `POST /api/v1/auth/login`: Đăng nhập bằng `username` hoặc `email`, trả về JWT Bearer Token.


* `GET /api/v1/auth/me`: Trả về thông tin tài khoản hiện tại từ JWT.



### 6.2. Nhóm Video & Phân tích (`/api/v1/videos`)

* `POST /api/v1/videos/submit`: Nhận URL video, lưu hoặc lấy bản ghi `videos`, tạo `analysis_runs` (`priority=1`) và đẩy vào `queue:high_priority`.


* `GET /api/v1/videos`: Danh sách các video do người dùng hiện tại gửi.


* `GET /api/v1/videos/{video_id}`: Xem chi tiết video và các quán ăn đã khớp (kiểm tra phân quyền, trả `404` nếu truy cập trái phép).


* `GET /api/v1/videos/analysis`: Lịch sử các lần yêu cầu phân tích của người dùng.


* `GET /api/v1/videos/analysis/{analysis_run_id}`: Xem trạng thái, `keyframes_data`, `ocr_data` và `execution_metrics` của một lượt chạy.



### 6.3. Nhóm Khám phá Bản đồ & Địa điểm (`/api/v1/places`)

* `GET /api/v1/places/nearby-videos`:
* **Query Params**: `lat` (float, bắt buộc), `lon` (float, bắt buộc), `radius_m` (float, mặc định `2000.0`, tối đa `50000`), `limit` (`20`), `offset` (`0`).


* **Xử lý**: Sử dụng hàm `ST_DWithin` và `ST_Distance` trên kiểu `Geography` của PostGIS để lọc và sắp xếp các video có quán ăn nằm trong bán kính từ gần đến xa. Nếu số lượng điểm trong vùng quá ít, kích hoạt ngầm tiến trình `DiscoveryService` đẩy link vào `queue:low_priority`.




* `GET /api/v1/places/search`: Tìm kiếm địa điểm theo từ khóa tên quán hoặc địa chỉ.


* `GET /api/v1/places/{place_id}`: Lấy thông tin chi tiết một địa điểm ăn uống.


* `GET /api/v1/places/{place_id}/videos`: Lấy toàn bộ video review của quán `place_id`, sắp xếp ưu tiên `confidence_status == 'HIGH'` lên đầu và thời gian mới nhất (`created_at DESC`).



### 6.4. Nhóm Lưu trữ Yêu thích (`/api/v1/saved`)

* **Saved Videos**:
* `POST /api/v1/saved/videos/{video_id}`: Lưu video yêu thích (hỗ trợ Idempotent: trả `201 Created` nếu mới, `200 OK` nếu đã lưu).


* `DELETE /api/v1/saved/videos/{video_id}`: Bỏ lưu video (`204 No Content`).


* `GET /api/v1/saved/videos`: Danh sách video đã lưu kèm địa điểm tương ứng, sắp xếp theo `created_at DESC`.




* **Saved Places**:
* `POST /api/v1/saved/places/{place_id}`: Lưu địa điểm yêu thích (Idempotent).


* `DELETE /api/v1/saved/places/{place_id}`: Bỏ lưu địa điểm (`204 No Content`).


* `GET /api/v1/saved/places`: Danh sách địa điểm đã lưu kèm tọa độ (`lat`, `lon`) và tổng số lượng video review (`video_count`) của từng quán.





---

## 7. QUY TẮC BẮT BUỘC DÀNH CHO AI CODING AGENT (STRICT CODING RULES)

1. **Phân tách tầng kiến trúc (Separation of Concerns)**:
* Các file trong `app/api/v1/endpoints/` chỉ nhận HTTP request, xác thực quyền qua `deps.py` và trả về Pydantic schema.


* Toàn bộ logic nghiệp vụ, gọi AI Server, Geocoding và truy vấn PostGIS phải đặt trong `app/services/`.




2. **Quy chuẩn tọa độ PostGIS (Longitude trước, Latitude sau)**:
* Mọi thao tác tạo điểm không gian với PostGIS và GeoAlchemy2 bắt buộc tuân thủ hệ tọa độ **WGS 84 (`SRID=4326`)** với thứ tự tham số là **Kinh độ (`lon`) trước, Vĩ độ (`lat`) sau**: `ST_MakePoint(lon, lat)` hoặc `POINT(lon lat)`.




3. **Bất đồng bộ hoàn toàn (Non-blocking I/O)**:
* Tuyệt đối không dùng thư viện đồng bộ `requests` bên trong các hàm `async def` của FastAPI; bắt buộc dùng `httpx.AsyncClient` cho cả AI Server và ArcGIS Geocoder.




4. **Quản lý cấu hình & Migration**:
* Mọi thay đổi trong `app/models/` phải đi kèm file migration Alembic (`alembic revision --autogenerate` và `alembic upgrade head`).


* Không hardcode URL, mật khẩu DB hay JWT secret trong code; đọc toàn bộ qua `app/core/config.py` từ file `.env`.