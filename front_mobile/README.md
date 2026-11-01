# Food Spot Mobile

Ứng dụng di động của dự án Food Spot, được phát triển bằng React Native, Expo và TypeScript.

## 1. Công nghệ

- React Native
- Expo
- TypeScript
- Expo Router

## 2. Cấu trúc thư mục

```text
front_mobile/
├── src/
│   └── app/
│       ├── _layout.tsx
│       ├── index.tsx
│       └── explore.tsx
├── assets/
├── components/
├── package.json
└── README.md
```

*Lưu ý: Cấu trúc trên là mô tả ban đầu; cập nhật theo các thư mục và file thực tế của dự án khi phát triển.*

## 3. Cài đặt

Yêu cầu Node.js và npm.

Mở terminal tại thư mục `front_mobile`:

```powershell
cd D:\PBL\front_mobile
```

Cài đặt các dependencies:

```powershell
npm install
```

## 4. Chạy ứng dụng

```powershell
npx expo start
```

Sau khi Expo khởi động, sử dụng QR code để mở ứng dụng bằng Expo Go tương thích, hoặc chạy trên Android Emulator nếu đã cấu hình.

## 5. Tiến độ

### Đã có

- Khởi tạo dự án Expo.
- Cấu hình React Native và TypeScript theo template.
- Sử dụng Expo Router cho điều hướng theo file.

### Đang phát triển / chưa xác nhận

- Giao diện và luồng nghiệp vụ Food Spot.
- Kết nối Backend.
- Đăng ký, đăng nhập.
- Phân tích video và tìm kiếm địa điểm.
- Lưu video, địa điểm và lịch sử.

Các chức năng nghiệp vụ sẽ được cập nhật vào README khi triển khai và kiểm thử thực tế.

## 6. Backend

Backend được phát triển riêng trong thư mục `../backend`.

Địa chỉ `http://127.0.0.1:8000` dùng để kiểm thử Backend trên cùng máy tính. Khi chạy ứng dụng trên điện thoại thật, cần cấu hình địa chỉ IP LAN của máy tính thay cho `127.0.0.1`.

## 7. Tài liệu tham khảo

- Expo: https://docs.expo.dev/
- Expo Router: https://docs.expo.dev/router/introduction/
- React Native: https://reactnative.dev/
