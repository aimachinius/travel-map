# Mô-đun Tính toán Độ phủ Hành chính & Phân giải Địa chỉ (Administrative Area Coverage & Address Resolver)

Mô-đun chuyên biệt cung cấp hai chức năng cốt lõi dựa trên dữ liệu bản đồ **OpenStreetMap (OSM)**:
1. **Phân giải địa chỉ hiện tại (Reverse Address Resolution)**: Bóc tách và hiển thị địa chỉ chi tiết tại vị trí tọa độ `(lat, lon)` bắt đầu từ cấp cơ sở **Phường / Xã** $\rightarrow$ **Quận / Huyện** $\rightarrow$ **Tỉnh / Thành phố** $\rightarrow$ **Quốc gia** (kèm tên đường/phố nếu có).
2. **Tính toán độ phủ đơn vị hành chính (District Coverage Calculation)**: Tính toán chính xác phần diện tích ($m^2$) và tỷ lệ bao phủ (%) của các đơn vị hành chính (`admin_level`) giao cắt với vùng bán kính hình tròn $r$ xung quanh tọa độ tìm kiếm.

---

## 1. Kiến trúc Hệ thống & Nguyên lý Toán học / GIS

### 1.1. Phép chiếu phẳng Azimuthal Equidistant (AEQD)
Do Trái Đất có dạng phỏng cầu, việc tính diện tích trực tiếp trên hệ tọa độ cầu WGS84 (`EPSG:4326` với đơn vị kinh vĩ độ) sẽ dẫn đến sai số rất lớn khi vĩ độ thay đổi. Mô-đun sử dụng phép chiếu phẳng cục bộ **Azimuthal Equidistant (`+proj=aeqd`)** lấy chính tọa độ tâm `(lat_0, lon_0)` làm gốc tọa độ `(0, 0)` theo đơn vị mét:

$$\text{CRS} = \texttt{+proj=aeqd +lat\_0=\{lat\} +lon\_0=\{lon\} +datum=WGS84 +units=m}$$

Đặc tính của phép chiếu này:
- Khoảng cách và tỷ lệ diện tích từ tâm tìm kiếm `(0, 0)` đi mọi hướng được bảo toàn chính xác tuyệt đối.
- Cho phép tạo vùng đệm bán kính chuẩn theo mét bằng thư viện Shapely:
  $$\text{Circle} = \text{Point}(0, 0).\text{buffer}(r, \text{quad\_segs}=64)$$
- Tổng diện tích hình tròn: $S_{\text{circle}} = \pi r^2$.

### 1.2. Dựng đa giác từ quan hệ OpenStreetMap (Relation Polygonization)
Một đơn vị hành chính trên OSM được biểu diễn bằng quan hệ (`relation`) chứa nhiều đoạn đường (`ways`) có vai trò `outer` (đường bao ngoài) và `inner` (đảo hoặc lỗ rỗng bên trong):
1. Thu thập các chuỗi tọa độ `geometry` từ tất cả các member thuộc kiểu `way`.
2. Hợp nhất các đường liên tục bằng toán tử `linemerge`.
3. Đa giác hóa thành các vòng khép kín bằng `polygonize`.
4. Hợp nhất thành đa giác hoàn chỉnh bằng `unary_union`.
5. Loại trừ các vùng rỗng `inner` bằng phép trừ không gian (`difference`).
6. Tự động khắc phục các lỗi hình học tự giao cắt (bowtie / self-intersection) bằng `shapely.make_valid()`.

### 1.3. Phép tính giao cắt & Tỷ lệ bao phủ (Spatial Intersection)
Với mỗi đa giác hành chính $P_i$ (đã được chiếu sang hệ mét):
1. Tính đa giác phần giao:
   $$I_i = \text{Circle} \cap P_i$$
2. Tính diện tích phần giao $S_i = \text{Area}(I_i)$ theo đơn vị mét vuông ($m^2$).
3. Tính tỷ lệ bao phủ:
   $$\text{Coverage}_i (\%) = \frac{S_i}{S_{\text{circle}}} \times 100$$
4. Sắp xếp kết quả giảm dần theo tỷ lệ phần trăm bao phủ.

### 1.4. Cơ chế Phân giải Địa chỉ Hiện tại 3 Lớp (3-Tier Address Resolution)
Để xác định địa chỉ chính xác bắt đầu từ cấp Phường/Xã tại tọa độ `(lat, lon)`, hệ thống tích hợp chuỗi dự phòng (fallback cascade):
1. **Lớp 1: Nominatim (Official OpenStreetMap API)**
   - Ngôn ngữ ưu tiên tiếng Việt (`accept-language=vi`).
   - Trích xuất chi tiết: `suburb` (Phường), `city_district` (Quận), `city` (Thành phố), `road` (Tuyến đường).
2. **Lớp 2: ArcGIS World Geocoding Service**
   - Kích hoạt khi Nominatim bị giới hạn tần suất hoặc phản hồi chậm.
   - Bóc tách theo `Neighborhood` (Phường), `District/City` (Quận), `Region` (Tỉnh/Thành phố).
3. **Lớp 3: Photon Komoot Geocoder**
   - Phản hồi cực nhanh (< 1 giây) từ bản trích xuất OSM.
4. **Bộ chuẩn hóa tiền tố hành chính Việt Nam (`_normalize_prefix`)**:
   - Tự động gắn tiền tố chuẩn mực: `Phường`, `Xã`, `Thị trấn`, `Quận`, `Huyện`, `Thành phố`, `Tỉnh`.
   - Ghép thành chuỗi địa chỉ tiêu chuẩn từ cấp Phường/Xã:
     $$\text{address\_from\_ward} = \text{"[Phường], [Quận], [Tỉnh/TP], Việt Nam"}$$

---

## 2. Cấu trúc Mô-đun trong Thư mục `area/`

```text
find/area/
├── __init__.py          # Export các API, Service, Model và hàm tiện ích
├── models.py            # Pydantic Schemas (DistrictCoverageRequest, DistrictCoverageItem, CurrentLocationAddress)
├── geometry.py          # Bounding Box WGS84, dựng đa giác Shapely từ OSM Relation
├── distance.py          # Tính khoảng cách mặt cầu Haversine (mét)
├── cache.py             # Bộ nhớ đệm TTL Cache (hỗ trợ phân tách key 'area:' và 'addr:', lưu file .cache_area.json)
├── service.py           # Core Service: Overpass Client racing, tính toán giao cắt Shapely, Fallback, Address Resolver
├── cli.py               # Giao diện dòng lệnh CLI chuẩn (Human table + JSON mode)
├── example_usage.py     # Script mẫu hướng dẫn tích hợp vào mã nguồn Python
├── .cache_area.json     # Tệp lưu trữ cache trên ổ đĩa (tự động tạo)
└── README.md            # Tài liệu đặc tả kỹ thuật chi tiết
```

---

## 3. Đặc tả Đầu vào & Đầu ra (Input / Output Schema)

### 3.1. Mô hình Dữ liệu Đầu vào (`DistrictCoverageRequest`)

| Thuộc tính | Kiểu dữ liệu | Bắt buộc | Mặc định | Ràng buộc / Mô tả |
| :--- | :---: | :---: | :--- | :--- |
| `lat` | `float` | **Có** | - | Vĩ độ tâm tìm kiếm. Ràng buộc: `[-90.0, 90.0]`. |
| `lon` | `float` | **Có** | - | Kinh độ tâm tìm kiếm. Ràng buộc: `[-180.0, 180.0]`. |
| `radius_m` | `float` | Không | `1500.0` | Bán kính hình tròn (mét). Ràng buộc: `> 0`. |
| `admin_level` | `str` | Không | `"6"` | Cấp hành chính OSM (`"4"`: Tỉnh/TP, `"6"`: Quận/Huyện, `"8"`: Phường/Xã). |

### 3.2. Mô hình Địa chỉ Vị trí Hiện tại (`CurrentLocationAddress`)

| Trường dữ liệu | Kiểu dữ liệu | Ví dụ | Mô tả |
| :--- | :---: | :--- | :--- |
| `lat` | `float` | `16.070373` | Vĩ độ của điểm đứng. |
| `lon` | `float` | `108.161783` | Kinh độ của điểm đứng. |
| `address_from_ward` | `str` | `"Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam"` | **Địa chỉ đầy đủ bắt đầu từ cấp Phường/Xã**. |
| `full_address` | `str` | `"Đường Hà Văn Tính, Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam"` | Địa chỉ chi tiết kèm tuyến đường (nếu có). |
| `ward` | `str \| null`| `"Phường Hòa Khánh Nam"` | Tên đơn vị cấp Phường/Xã (đã chuẩn hóa tiền tố). |
| `district` | `str \| null`| `"Quận Liên Chiểu"` | Tên đơn vị cấp Quận/Huyện (đã chuẩn hóa tiền tố). |
| `city` | `str \| null`| `"Thành phố Đà Nẵng"` | Tên Tỉnh / Thành phố trực thuộc Trung ương. |
| `country` | `str` | `"Việt Nam"` | Quốc gia. |
| `road` | `str \| null`| `"Đường Hà Văn Tính"` | Tên đường / tuyến phố nếu phát hiện được. |

### 3.3. Mô hình Đơn vị Hành chính Giao cắt (`DistrictCoverageItem`)

| Trường dữ liệu | Kiểu dữ liệu | Ví dụ | Mô tả |
| :--- | :---: | :--- | :--- |
| `osm_id` | `int` | `19403874` | ID định danh của quan hệ ranh giới trên OpenStreetMap. |
| `name` | `str` | `"Quận Liên Chiểu"` | Tên đầy đủ của đơn vị hành chính. |
| `admin_level` | `str` | `"6"` | Cấp hành chính tương ứng. |
| `area_m2` | `float` | `19242255.0` | Diện tích giao cắt với hình tròn bán kính $r$ (làm tròn 1 chữ số thập phân). |
| `percentage` | `float` | `50.0` | Tỷ lệ phần trăm bao phủ so với tổng diện tích hình tròn (%). |

---

## 4. Hướng dẫn Sử dụng Giao diện Dòng lệnh (CLI)

Chương trình có thể được gọi trực tiếp bằng tệp `cli.py` trong thư mục `area/` hoặc thông qua wrapper `cli_area.py` ở thư mục cha.

### 4.1. Cú pháp Lệnh

```powershell
# Chạy trực tiếp từ thư mục find/area:
python cli.py --lat <LAT> --lon <LON> --radius <RADIUS> [--admin-level <LEVEL>] [--json] [--no-cache]

# Hoặc chạy từ thư mục find/:
python cli_area.py --lat <LAT> --lon <LON> --radius <RADIUS>
```

### 4.2. Các Tham số Hỗ trợ

| Cờ (Flag) | Kiểu dữ liệu | Mặc định | Ý nghĩa |
| :--- | :---: | :---: | :--- |
| `--lat` | `float` | `21.0056` | Vĩ độ điểm tìm kiếm (Mặc định: ĐH Bách Khoa Hà Nội). |
| `--lon` | `float` | `105.8433` | Kinh độ điểm tìm kiếm (Mặc định: ĐH Bách Khoa Hà Nội). |
| `--radius` | `float` | `1500.0` | Bán kính quét tính theo mét. |
| `--admin-level` | `str` | `"6"` | Cấp hành chính cần tính diện tích (`4`: Tỉnh/TP, `6`: Quận/Huyện, `8`: Phường/Xã). |
| `--endpoint` | `str` | `None` | Chỉ định URL Overpass Server tùy chọn. |
| `--no-cache` | `flag` | `False` | Bỏ qua dữ liệu trong cache, ép buộc truy vấn mới. |
| `--json` | `flag` | `False` | Xuất dữ liệu dưới dạng JSON nguyên bản thay vì bảng văn bản. |

### 4.3. Ví dụ Kết quả Terminal (Standard Text Table)

```powershell
python cli.py --lat 16.070373 --lon 108.161783 --radius 2500
```

**Kết quả hiển thị trên màn hình:**

```text
================================================================================
VỊ TRÍ HIỆN TẠI (CURRENT LOCATION):
  Tọa độ (Coordinates)     : 16.070373, 108.161783
  Tuyến đường (Street)     : Đường Hà Văn Tính
  Địa chỉ (Từ cấp Phường)  : Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam
  Địa chỉ chi tiết đầy đủ  : Đường Hà Văn Tính, Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam
================================================================================

Đang tính toán phạm vi bao phủ (admin_level=6) trong bán kính 2500.0m quanh (16.070373, 108.161783)...

Found 4 intersecting administrative units (admin_level=6):
================================================================================
No.  | District Name                | OSM ID       | Area (m²)      | Coverage (%)
--------------------------------------------------------------------------------
1    | Phường Hòa Khánh             | 14651840     | 9,409,189.7    | 47.93%
2    | Phường Liên Chiểu            | 15848509     | 3,301,596.2    | 16.82%
3    | Phường Thanh Khê             | 13995327     | 2,831,294.7    | 14.42%
4    | Phường An Khê                | 13981042     | 977,053.8      | 4.98%
================================================================================
© OpenStreetMap contributors
```

### 4.4. Ví dụ Kết quả JSON (`--json`)

```powershell
python cli.py --lat 16.070373 --lon 108.161783 --radius 2500 --json
```

```json
{
  "current_location": {
    "lat": 16.070373,
    "lon": 108.161783,
    "address_from_ward": "Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam",
    "full_address": "Đường Hà Văn Tính, Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam",
    "ward": "Phường Hòa Khánh Nam",
    "district": "Quận Liên Chiểu",
    "city": "Thành phố Đà Nẵng",
    "country": "Việt Nam",
    "road": "Đường Hà Văn Tính"
  },
  "query": {
    "lat": 16.070373,
    "lon": 108.161783,
    "radius_m": 2500.0,
    "admin_level": "6"
  },
  "attribution": "© OpenStreetMap contributors",
  "districts_count": 4,
  "results": [
    {
      "osm_id": 14651840,
      "name": "Phường Hòa Khánh",
      "admin_level": "6",
      "area_m2": 9409189.7,
      "percentage": 47.93
    },
    {
      "osm_id": 15848509,
      "name": "Phường Liên Chiểu",
      "admin_level": "6",
      "area_m2": 3301596.2,
      "percentage": 16.82
    },
    {
      "osm_id": 13995327,
      "name": "Phường Thanh Khê",
      "admin_level": "6",
      "area_m2": 2831294.7,
      "percentage": 14.42
    },
    {
      "osm_id": 13981042,
      "name": "Phường An Khê",
      "admin_level": "6",
      "area_m2": 977053.8,
      "percentage": 4.98
    }
  ]
}
```

---

## 5. Hướng dẫn Tích hợp vào Ứng dụng Python (Python API)

### 5.1. Tra cứu Địa chỉ Hiện tại từ Cấp Phường/Xã

```python
from find.area import resolve_current_address

# Tọa độ tại Đà Nẵng
lat, lon = 16.070373, 108.161783
addr = resolve_current_address(lat, lon)

print("Địa chỉ hành chính:", addr["address_from_ward"])
# -> "Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam"

print("Địa chỉ chi tiết  :", addr["full_address"])
# -> "Đường Hà Văn Tính, Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam"
```

### 5.2. Tính toán Diện tích Phủ các Quận/Huyện

```python
from find.area import get_district_coverage

results = get_district_coverage(
    lat=16.070373,
    lon=108.161783,
    radius_m=3500,
    admin_level="6",  # Cấp Quận/Huyện
)

for item in results:
    print(f"{item['name']:<20}: {item['percentage']}% ({item['area_m2']:,} m²)")
```

### 5.3. Sử dụng Object-Oriented Service & Pydantic Models

```python
from find.area import DistrictCoverageRequest, DistrictCoverageService

request = DistrictCoverageRequest(
    lat=21.0056,
    lon=105.8433,
    radius_m=1500,
    admin_level="6",
)

service = DistrictCoverageService(use_cache=True)
items = service.calculate_coverage(request)

for it in items:
    print(it.name, it.percentage, it.area_m2)
```

---

## 6. Chính sách Bộ nhớ đệm (Caching Policy)

Mô-đun sử dụng lớp `TTLCache` với các cơ chế:
- **Khóa bộ nhớ đệm (Cache Keys)**:
  - Khóa độ phủ: `area:{lat}:{lon}:{radius_m}:{admin_level}` (tọa độ làm tròn 4 chữ số thập phân ~11m).
  - Khóa địa chỉ: `addr:{lat}:{lon}` (thời hạn mặc định 24 giờ).
- **Lưu trữ xuống đĩa (.cache_area.json)**: Đảm bảo dữ liệu không bị mất khi ứng dụng khởi động lại, giảm tải tối đa số lần gọi ra máy chủ công cộng OSM.
- **Tự động dọn dẹp**: Các bản ghi hết hạn (expired) sẽ tự động bị loại bỏ khi khởi tạo hoặc khi dung lượng vượt quá ngưỡng `max_entries=256`.

