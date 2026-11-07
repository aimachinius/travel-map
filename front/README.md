# Food Spot Frontend

Frontend Web của dự án Food Spot, được xây dựng bằng React và TypeScript. Giao diện hỗ trợ người dùng khám phá địa điểm ăn uống, tìm kiếm video review và quản lý nội dung đã lưu.

## 1. Công nghệ sử dụng

- **React**: Xây dựng giao diện người dùng.
- **TypeScript**: Kiểm soát kiểu dữ liệu.
- **Vite**: Công cụ khởi tạo và chạy ứng dụng.
- **React Router**: Quản lý điều hướng giữa các trang.
- **CSS**: Xây dựng giao diện và bố cục.
- **React Leaflet**: Hiển thị bản đồ.
- **OpenStreetMap / CARTO**: Nguồn bản đồ nền.

## 2. Cấu trúc thư mục

```text
front/
├── public/
│   └── food-spot.svg
│
├── src/
│   ├── app/
│   ├── components/
│   ├── mocks/
│   │   └── mockAuth/
│   ├── pages/
│   │   ├── MainLayout.tsx
│   │   ├── FoodSpotLanding.tsx
│   │   ├── Login.tsx
│   │   ├── Register.tsx
│   │   ├── Explore.tsx
│   │   ├── SavedVideos.tsx
│   │   └── SavedPlaces.tsx
│   │
│   └── ...
│
├── index.html
├── package.json
├── package-lock.json
└── README.md
```

*Lưu ý: Cấu trúc trên mô tả các thư mục và file chính. Các file component, CSS và cấu hình khác được giữ theo cấu trúc thực tế trong repository.*

## 3. Các trang và chức năng đã triển khai

| Trang | Chức năng |
|---|---|
| Landing | Trang giới thiệu Food Spot |
| Login | Giao diện đăng nhập |
| Register | Giao diện đăng ký |
| Explore | Trang khám phá địa điểm và bản đồ |
| Saved Videos | Trang video đã lưu |
| Saved Places | Trang địa điểm đã lưu |
| MainLayout | Bố cục chính và thanh điều hướng |

### Điều hướng

Các route hiện có:

| Route | Trang |
|---|---|
| `/` | Landing |
| `/login` | Đăng nhập |
| `/register` | Đăng ký |
| `/explore` | Khám phá |
| `/home` | Chuyển hướng đến `/explore` |
| `/saved-videos` | Video đã lưu |
| `/saved-places` | Địa điểm đã lưu |
| `/history` | Trang placeholder, chuyển hướng đến `/explore` |
| `/settings` | Trang placeholder, chuyển hướng đến `/explore` |

### Giao diện chính

- Thanh điều hướng bên cạnh (Sidebar).
- Logo Food Spot.
- Các mục điều hướng giữa những trang chính.
- Menu tài khoản và chức năng đăng xuất.
- Giao diện sử dụng tông màu xanh lá.
- Bố cục thích ứng với kích thước màn hình.

### Bản đồ

- Sử dụng React Leaflet.
- Hiển thị bản đồ nền từ CARTO Voyager.
- Hỗ trợ hiển thị vị trí trên bản đồ.
- Có thể phát triển thêm chức năng tìm kiếm và chọn vị trí.

## 4. Trạng thái triển khai

### Đã hoàn thiện (Production Ready trên Docker)

- **Kiến trúc & Công nghệ**: React 19 + TypeScript + Vite + Nginx Alpine chạy Docker Compose.
- **Xác thực tài khoản (Auth)**: Kết nối 100% với FastAPI Backend qua JWT Bearer Token (`/api/v1/auth/register`, `/login`, `/me`).
- **Bản đồ Khám phá (Map Discovery)**: Kết nối API không gian PostGIS `GET /api/v1/places/nearby-videos` hiển thị trực tiếp quán ăn và video review theo bán kính và tọa độ (mặc định Đà Nẵng, chuyển đổi linh hoạt qua các thành phố khác hoặc GPS thiết bị).
- **Phân tích Video AI thời gian thực**: Gửi URL TikTok/YouTube qua `POST /api/v1/videos/submit`, điều phối qua hàng đợi Redis và lắng nghe tiến trình nhận diện tự động qua WebSocket `/api/v1/ws`.
- **Ngăn kéo kính thể lỏng (Liquid Drawer)**: Hiển thị danh sách Video đã lưu (`/api/v1/saved/videos`), Quán ăn đã lưu (`/api/v1/saved/places`) và Lịch sử các lần phân tích AI (`/api/v1/videos/analysis`).
- **Chỉ đường thông minh**: Tích hợp công cụ chỉ đường OSRM client-side miễn phí 100% cho xe máy và ô tô.
- **Reverse Proxy**: Nginx cấu hình sẵn `proxy_pass http://backend:8000;` tự động chuyển tiếp request `/api/` mượt mà, không gặp lỗi CORS.

## 5. Yêu cầu môi trường

- Node.js (phiên bản tương thích với dependencies trong `package.json`).
- npm.
- Git.
- Visual Studio Code hoặc IDE tương đương.

## 6. Hướng dẫn cài đặt và chạy

### Bước 1. Clone repository

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY_FOLDER>/front
```

### Bước 2. Cài đặt dependencies

```bash
npm install
```

### Bước 3. Chạy ứng dụng

```bash
npm run dev
```

Vite sẽ hiển thị địa chỉ local trong terminal, thông thường là:

```text
http://localhost:5173
```

Mở địa chỉ này trên trình duyệt để sử dụng frontend.

## 7. Lưu ý khi phát triển chung

- Không commit thư mục `node_modules/`.
- Không commit các file build như `dist/`.
- Không tự ý thay đổi cấu trúc route nếu chưa thống nhất với nhóm.
- Các chức năng cần dữ liệu thật phải kết nối API backend thay vì sử dụng mock data.
- Khi thêm API, nên tách phần gọi API khỏi component giao diện.
- Khi thêm trang mới, cần cập nhật cấu hình điều hướng tương ứng.

---

**Trạng thái hiện tại:** Frontend Web đã có cấu trúc React + TypeScript, các trang giao diện chính và điều hướng cơ bản. Các chức năng cần dữ liệu thực tế vẫn đang chờ tích hợp với Backend và các module AI của dự án.