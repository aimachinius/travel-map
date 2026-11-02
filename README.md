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

- **Build lại backend**:
  ```bash
  docker compose build backend
  docker compose up -d backend
  ```
- **Build lại frontend**:
  ```bash
  docker compose build front
  docker compose up -d front  
  ```

- **Build lại mock-ai**:
  ```bash
  docker compose build mock-ai
  docker compose up -d mock-ai
  ```
