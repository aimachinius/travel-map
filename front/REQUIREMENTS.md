# Yêu Cầu Cài Đặt và Thư Viện (Frontend Requirements)

Tài liệu này tổng hợp toàn bộ các yêu cầu môi trường, thư viện phụ thuộc (dependencies) cần thiết cho dự án **Food Spot Frontend** đã được kiểm tra tính tương thích, đảm bảo **không xảy ra xung đột peer-dependencies** và build thành công 100%.

---

## 1. Yêu Cầu Môi Trường (System / Runtime Requirements)

- **Node.js**: Phiên bản **>= 18.0.0** (Khuyến nghị **Node.js 20 LTS** hoặc **Node.js 22 LTS**).
- **npm**: Phiên bản **>= 9.0.0** (hoặc yarn / pnpm tương đương).
- **Trình duyệt hỗ trợ**: Chrome, Firefox, Edge, Safari các phiên bản hiện đại (hỗ trợ ESModules và WebGL/Canvas cho bản đồ).

---

## 2. Danh Sách Thư Viện & Phiên Bản Đã Kiểm Thử Tương Thích

### 2.1. Thư viện chạy ứng dụng (Production Dependencies)

| Tên thư viện | Phiên bản | Mục đích & Sử dụng trong dự án |
| :--- | :--- | :--- |
| **`react`** | `^19.2.8` | Thư viện cốt lõi xây dựng giao diện người dùng |
| **`react-dom`** | `^19.2.8` | Renderer React dành cho trình duyệt web |
| **`react-router-dom`** | `^7.18.4` | Định tuyến SPA (`/explore`, `/login`, `/register`, `/saved-places`, `/saved-videos`,...) |
| **`leaflet`** | `^1.9.4` | Thư viện bản đồ tương tác mã nguồn mở |
| **`react-leaflet`** | `^5.0.0` | React wrapper cho Leaflet (tương thích hoàn toàn với React 19) |
| **`lucide-react`** | `^1.61.0` | Bộ icon SVG hỗ trợ giao diện |

### 2.2. Thư viện hỗ trợ phát triển & biên dịch (Dev Dependencies)

| Tên thư viện | Phiên bản | Mục đích & Sử dụng trong dự án |
| :--- | :--- | :--- |
| **`vite`** | `^8.3.0` | Công cụ build và máy chủ phát triển (Dev Server) tốc độ cao |
| **`@vitejs/plugin-react`** | `^6.1.1` | Plugin Fast Refresh cho React trên Vite |
| **`typescript`** | `~6.0.2` | Ngôn ngữ kiểm soát kiểu dữ liệu tĩnh |
| **`@types/react`** | `^19.2.18` | Định nghĩa kiểu TypeScript cho React 19 |
| **`@types/react-dom`** | `^19.2.7` | Định nghĩa kiểu TypeScript cho React-DOM 19 |
| **`@types/leaflet`** | `^1.9.22` | Định nghĩa kiểu TypeScript cho thư viện bản đồ Leaflet |
| **`@types/node`** | `^24.13.3` | Định nghĩa kiểu môi trường Node.js |
| **`oxlint`** | `^1.81.0` | Công cụ lint kiểm tra chất lượng mã nguồn siêu nhanh |

---

## 3. Hướng Dẫn Cài Đặt (Không Xung Đột)

### Cách 1: Cài đặt chuẩn xác theo `package-lock.json` (Khuyên dùng)
Dự án đã có sẵn `package.json` và `package-lock.json` đã được resolve chính xác toàn bộ cây phụ thuộc:

```bash
# Cách khuyên dùng để cài đúng 100% phiên bản không bị sai lệch:
npm ci

# Hoặc:
npm install
```

### Cách 2: Lệnh cài đặt thủ công từ đầu (Nếu tạo mới hoặc cài lại)

Nếu bạn muốn cài đặt trực tiếp từng gói bằng lệnh npm:

```bash
# 1. Cài đặt các thư viện chính (Dependencies)
npm install react@^19.2.8 react-dom@^19.2.8 react-router-dom@^7.18.4 leaflet@^1.9.4 react-leaflet@^5.0.0 lucide-react@^1.61.0

# 2. Cài đặt các thư viện phát triển (Dev Dependencies)
npm install -D vite@^8.3.0 @vitejs/plugin-react@^6.1.1 typescript@~6.0.2 @types/react@^19.2.18 @types/react-dom@^19.2.7 @types/leaflet@^1.9.22 @types/node@^24.13.3 oxlint@^1.81.0
```

---

## 4. Cấu Hình Biến Môi Trường (`.env`)

Tạo file `.env` tại thư mục gốc của frontend (dựa theo `.env.example`):

```env
# Địa chỉ Backend API
VITE_API_BASE_URL=http://localhost:8000

# Khóa API CARTO Tiles (nếu có yêu cầu từ nhà cung cấp bản đồ)
VITE_CARTO_API_KEY=
```

---

## 5. Các Lệnh Thực Thi Dự Án

| Lệnh | Chức năng |
| :--- | :--- |
| `npm run dev` | Khởi chạy server phát triển tại cục bộ (`http://localhost:5173`) |
| `npm run build` | Biên dịch TypeScript và đóng gói bản phát hành (`dist/`) |
| `npm run preview`| Chạy thử bản build production tại máy local |
| `npm run lint` | Quét kiểm tra lỗi cú pháp và code style bằng Oxlint |

---

## 6. Trạng Thái Kiểm Thử
- **`npm install`**: Đã kiểm tra -> 0 xung đột (0 vulnerabilities).
- **`npm run build`**: Đã kiểm tra (`tsc -b && vite build`) -> Biên dịch thành công 100%.
- **`npm run lint`**: Đã kiểm tra -> 0 warnings, 0 errors.

