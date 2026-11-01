### Lệnh sử dụng docker 

- **Khởi động toàn bộ**:
  ```bash
  docker compose up -d
  ```
- **Xem logs**:
  ```bash
  docker compose logs -f backend
  docker compose logs -f front
  ```
- **Chạy lại unit test**:
  ```bash
  docker compose exec backend pytest
  ```
- **Dừng hệ thống**:
  ```bash
  docker compose down
  ```

