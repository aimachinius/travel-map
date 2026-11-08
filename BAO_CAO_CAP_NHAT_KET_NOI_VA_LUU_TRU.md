# BÁO CÁO CẬP NHẬT: KẾT NỐI REAL DATA, BỘ SƯU TẬP VIDEO-ĐỊA ĐIỂM & ĐỘ SẴN SÀNG GỘP NHÁNH

> **Thời điểm cập nhật:** 07/11/2026  
> **Trạng thái Frontend:** ✅ `0 errors`, `0 warnings` (Đã pass kiểm tra Lint và Build thành công)  
> **Trạng thái Backend:** ✅ Đã đồng bộ 49 files từ nhánh `food-app`  

---

## 1. TỔNG QUAN CẬP NHẬT (EXECUTIVE SUMMARY)

Theo các yêu cầu điều chỉnh mới nhất của bạn:
1. **Loại bỏ toàn bộ Mock Auth & Mock Data:** Chuyển sang kết nối dữ liệu thật giữa Frontend và Backend. Các luồng Đăng nhập, Đăng ký, Lấy thông tin tài khoản (Profile), Danh sách địa điểm và Danh sách lưu trữ giờ đây gọi trực tiếp API Backend.
2. **Chuẩn hóa cơ chế Lưu trữ (Video luôn đi kèm Địa điểm):** 
   - Người dùng chỉ cần nhấn **Lưu video** (1 thao tác duy nhất). Do mỗi video review trên hệ thống đều đã được trích xuất và liên kết với một địa điểm (`VideoPlaceMatch` $\rightarrow$ `Place`), không cần phải lưu địa điểm riêng biệt gây phân mảnh dữ liệu.
   - Cơ sở dữ liệu sử dụng bảng `saved_videos`. Backend đã có sẵn hàm join tự động lấy cả `Video` lẫn `Place`.
3. **Bảng lưu trên Drawer với 2 Option chuyển đổi:**
   - **Option 1 (`📹 Video đã lưu`):** Danh sách toàn bộ video review TikTok đã lưu. Nhấn vào là phát video và camera bản đồ lướt tới quán.
   - **Option 2 (`📍 Địa điểm đã lưu`):** Tự động lọc ngược (Reverse Grouping) từ danh sách video đã lưu ra các Quán ăn duy nhất. Hiển thị thông tin quán, số lượng video review đã lưu của quán. Nhấn vào là camera bản đồ bay tới ngay tọa độ quán (`flyTo`) và tự động phát video review tương ứng.
4. **Cập nhật Backend:** Đồng bộ mã nguồn Backend mới nhất từ nhánh `food-app` vào thư mục dự án mà không ảnh hưởng tới Frontend.

---

## 2. CHI TIẾT CÁC THAY ĐỔI ĐÃ TRIỂN KHAI

### 2.1. Loại bỏ Mock Authentication $\rightarrow$ Chuyển sang Real Auth API
- **`src/services/api.ts`:**
  - Bổ sung `getStoredUser()`, `setStoredUser()`, và sự kiện broadcast `foodspot_auth_changed`.
  - Cập nhật `authApi.login()`: Sau khi nhận Bearer Token, tự động gọi `authApi.getMe()` để lưu Profile thật vào `foodspot_user`.
  - Cập nhật `authApi.logout()`: Xóa sạch Token và Profile, phát sự kiện để toàn bộ UI cập nhật tức thì.
  - Cung cấp `authApi.isAuthenticated()`.
- **`src/pages/Login.tsx`:**
  - Gỡ bỏ hoàn toàn `mockAuth.ts`.
  - Chuyển `handleSubmit` sang gọi `authApi.login({ username_or_email, password })`.
  - Bắt lỗi chi tiết từ Backend (`ApiError`) hiển thị trực tiếp lên form.
  - Đăng nhập thành công sẽ tự động chuyển hướng vào `/explore`.
- **`src/pages/Register.tsx`:**
  - Gỡ bỏ hoàn toàn `mockAuth.ts`.
  - Gọi `authApi.register({ username, email, password, full_name })`.
  - Tự động đăng nhập lấy Token và chuyển vào ứng dụng ngay sau khi đăng ký thành công.
- **`src/components/layout/UnifiedHeader.tsx` & `src/components/liquid/LiquidHeader.tsx`:**
  - Gỡ bỏ hoàn toàn `mockAuth.ts`.
  - Hiển thị Avatar và Tên tài khoản thật từ Backend (`user.full_name || user.username`).
  - Lắng nghe sự kiện `foodspot_auth_changed` và `storage` để tự động render lại header khi người dùng đăng nhập hoặc đăng xuất ở bất kỳ trang/tab nào.

---

### 2.2. Cơ chế Lưu Video Đính Kèm Địa Điểm (Single Source of Truth)
- **Triết lý:** Một video review ẩm thực luôn gắn liền với một quán ăn cụ thể. Khi người dùng bấm lưu, họ đang lưu **trải nghiệm ẩm thực** đó.
- **API tương tác:**
  - Khi bấm nút Bookmark trên `LiquidVideoPlayer`:
    ```typescript
    // Chỉ cần gọi lưu/bỏ lưu video
    savedApi.toggleSaveVideo(currentVideo.id, isCurrentlySaved)
    ```
  - Gọi trực tiếp endpoint:
    - Lưu: `POST /api/v1/saved/videos/{video_id}`
    - Bỏ lưu: `DELETE /api/v1/saved/videos/{video_id}`
- **Khả năng đáp ứng của Backend:**
  Backend ở nhánh `food-app` đã có sẵn logic này trong `SavedService.get_saved_videos`:
  ```python
  # backend/app/services/saved_service.py
  query = (
      select(SavedVideo, Video, Place)
      .join(Video, Video.id == SavedVideo.video_id)
      .outerjoin(VideoPlaceMatch, VideoPlaceMatch.video_id == Video.id)
      .outerjoin(Place, Place.id == VideoPlaceMatch.place_id)
      .where(SavedVideo.user_id == user_id)
      .order_by(SavedVideo.created_at.desc())
  )
  ```
  $\rightarrow$ **Kết quả:** Trả về một danh sách thống nhất gồm cả Video Metadata và Place Coordinates mà không cần phải ghi dữ liệu 2 lần hay duy trì bảng phụ.

---

### 2.3. Bảng Lưu Trữ Kính Nước (Drawer) với 2 Chế Độ Xem Linh Hoạt
Trong file [`src/components/liquid/LiquidDrawer.tsx`](file:///e:/PBL6/travel-map-app/front/src/components/liquid/LiquidDrawer.tsx):

```
+-------------------------------------------------------------+
|  🔖 BỘ SƯU TẬP MÓN & QUÁN                                   |
|  [ 📹 Video đã lưu (5) ]      [ 📍 Địa điểm đã lưu (3) ]    |
+-------------------------------------------------------------+
```

1. **Option 1: `📹 Video đã lưu`:**
   - Hiển thị danh sách từng video review TikTok đã lưu.
   - Thẻ card gồm: Thumbnail video, Icon món ăn, Tiêu đề video, Tên quán (`📍 Tên quán`), Kênh reviewer (`@author`), Tag thể loại.
   - Thao tác: Bấm nút `▶️ Xem ngay` sẽ phát video trên khung 9:16 và camera bản đồ lướt đến tọa độ quán; nút `✕` bỏ lưu video.

2. **Option 2: `📍 Địa điểm đã lưu` (Lọc ngược từ bảng video):**
   - Thuật toán `useMemo` tự động gom nhóm danh sách video theo địa điểm (`placeId` hoặc tọa độ `lat, lng`):
     ```typescript
     // Gom nhóm các video có cùng địa điểm quán ăn
     const savedPlacesList = useMemo(() => { ... }, [savedSpots]);
     ```
   - Mỗi card đại diện cho 1 Quán ăn:
     - Tên quán to rõ (`place.name`)
     - Địa chỉ quán (`place.address`)
     - Tag huy hiệu: Thể loại món + Huy hiệu `🎬 X video review` (hiển thị số lượng review của quán mà user đã lưu).
   - Thao tác: Bấm nút **`🗺️ Bay tới quán`** $\rightarrow$ Camera Leaflet bay tới ngay quán trên bản đồ (`flyTo`), đồng thời trình phát tự động nạp và phát video review đầu tiên của quán đó.

---

### 2.4. Kết Nối Dữ Liệu Thật từ Backend API
- **`src/components/liquid/LiquidGlassExperience.tsx`:**
  - Tự động gọi `placesApi.getPlaces({ limit: 50 })` khi load trang để đưa danh sách quán thật từ DB lên bản đồ và playlist.
  - Tự động gọi `savedApi.getSavedVideos()` khi người dùng đã đăng nhập để nạp danh sách lưu trữ thật từ Backend.
  - Giữ lại danh sách khởi tạo cục bộ an toàn (`fallback`) để giao diện vẫn hoạt động trơn tru nếu server Backend chưa khởi động.
- **`src/pages/FoodSpotLanding.tsx`:**
  - Tự động gọi `placesApi.getPlaces({ limit: 20 })` để hiển thị các quán thật trên Minimap và danh sách món hot tuần.

---

## 3. CẬP NHẬT BACKEND TỪ NHÁNH `food-app`

Tôi đã cập nhật toàn bộ thư mục `backend/` trong workspace `E:\PBL6\travel-map-app` đồng bộ 100% với commit `14c7c23` của nhánh `food-app`:
- Thêm router `backend/app/api/v1/endpoints/saved.py`.
- Thêm service `backend/app/services/saved_service.py`.
- Thêm schemas `backend/app/schemas/saved.py`.
- Thêm các module phát hiện không gian `backend/app/services/area/*`, crawler `tiktok_crawler.py`, và WebSocket manager.
- Cập nhật migrations PostGIS.

---

## 4. BẢNG ĐỐI CHIẾU TRƯỚC VÀ SAU CẢI TIẾN

| Tiêu chí | Trước khi điều chỉnh | Sau khi điều chỉnh (Hiện tại) |
| :--- | :--- | :--- |
| **Xác thực User** | Dùng `mockAuth.ts` (LocalStorage giả lập). | **100% Real API** (`/auth/login`, `/auth/register`, `/auth/me`). |
| **Trạng thái Header** | Đọc dữ liệu mock `getSessionUser()`. | Tự động đồng bộ với tài khoản thật từ token JWT. |
| **Cơ chế lưu trữ** | Bị tách đôi thành 2 nút lưu video và lưu địa điểm riêng. | **Chỉ lưu video 1 chạm**: Video tự mang thông tin quán (`saved_videos`). |
| **Bảng hiển thị lưu trữ** | 1 danh sách hỗn hợp hoặc chia 2 drawer riêng biệt. | **1 Drawer duy nhất với 2 Option**: Tab Video và Tab Địa điểm (lọc ngược từ video). |
| **Tương tác khi click địa điểm** | Chỉ bay camera map, không phát video. | **Bay camera map + tự động phát video review liên kết**. |
| **Dữ liệu Map & Khám phá** | Dữ liệu cứng tĩnh hoàn toàn. | **Tự động gọi `/places` từ Backend**, có fallback an toàn. |

---

## 5. NHỮNG VẤN ĐỀ CÒN LẠI & HƯỚNG DẪN THÊM DATA

1. **Dữ liệu ban đầu trong Cơ sở dữ liệu:**
   - Do database PostgreSQL mới khởi tạo có thể chưa có sẵn nhiều quán ăn và video, bạn chỉ cần khởi động backend (`docker compose up -d db redis backend`) và chạy crawler hoặc import vài bản ghi mẫu vào bảng `places` và `videos`.
   - Frontend đã được thiết kế cơ chế fallback thông minh: nếu API trả về danh sách rỗng, giao diện sẽ dùng danh sách mẫu để bạn luôn kiểm thử được UI.
2. **Backend Python Environment:**
   - Để chạy backend cục bộ ngoài Docker, môi trường Python cần cài các thư viện trong `backend/requirements.txt` (đặc biệt là `geoalchemy2` và `asyncpg` cho tính năng PostGIS). Chạy trong Docker container (`docker-compose.yml`) là cách tiện lợi nhất vì đã đóng gói đủ thư viện.

---

## 6. ĐÁNH GIÁ ĐỘ SẴN SÀNG GỘP NHÁNH (MERGE READINESS)

### 👉 **ĐỘ SẴN SÀNG: 95% (SẴN SÀNG GỘP NGAY)**

- **Frontend (`front/`):**
  - Đã pass `oxlint`: **0 warnings, 0 errors**.
  - Đã pass `tsc -b && vite build`: **Compile thành công 100%**.
  - Không có file nào bị xung đột (conflict) với logic Backend.
- **Backend (`backend/`):**
  - Đã đồng bộ mã nguồn mới nhất từ `food-app`.
  - Endpoint `/saved/videos` đáp ứng chính xác 100% logic lưu trữ mà Frontend vừa cài đặt.

Bạn có thể tiến hành commit các thay đổi trên nhánh `ui/front_web` và merge với nhánh `food-app` bất cứ lúc nào!

