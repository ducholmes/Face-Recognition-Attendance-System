# Hệ Thống Điểm Danh Bằng Nhận Diện Khuôn Mặt (Face Recognition Attendance System)

## Giới Thiệu
Hệ thống điểm danh tự động sử dụng công nghệ nhận diện khuôn mặt. Dự án áp dụng AI để phát hiện, trích xuất đặc trưng khuôn mặt và xác nhận danh tính người dùng một cách chính xác.

## Kiến Trúc và Các Thành Phần Của Dự Án
Hệ thống bao gồm các thành phần chính:
1. **Frontend (`app`)**: Giao diện web người dùng (UI) và Proxy, chạy trên cổng `5001`.
2. **Backend API (`api`)**: Xử lý logic nghiệp vụ, quản lý cơ sở dữ liệu và xác thực, chạy trên cổng `8000`.
3. **Face Service (`face`)**: Xử lý hình ảnh, phát hiện và nhận diện khuôn mặt AI, chạy trên cổng `5000`.
4. **Task Queue (`worker` & `redis`)**: Xử lý các tác vụ ngầm bất đồng bộ.
5. **Reverse Proxy (`nginx`)**: Điều phối lưu lượng mạng.

---

## Hướng Dẫn Sử Dụng và Chạy Dự Án

Bạn có 2 cách để truy cập và sử dụng hệ thống này:

### Cách 1: Truy cập trực tiếp (Không cần cài đặt)
Bạn có thể trải nghiệm ngay hệ thống thông qua đường link công khai (đã được host ngrok):
👉 **https://result-bulge-grievance.ngrok-free.dev/**

### Cách 2: Chạy trên máy cá nhân (Localhost) bằng Docker Compose
Nếu muốn tự triển khai, bạn chỉ cần Docker và Docker Compose.

**Bước 1:** Sao chép file `.env.example` thành `.env` và cấu hình các biến cần thiết (nếu chưa có):
```bash
cp .env.example .env
```

**Bước 2:** Khởi chạy toàn bộ hệ thống bằng Docker Compose:
```bash
docker-compose up --build -d
```

**Bước 3:** Truy cập vào ứng dụng trên trình duyệt web của bạn:
👉 **http://localhost:5001**

Để dừng hệ thống khi không sử dụng nữa:
```bash
docker-compose down
```
