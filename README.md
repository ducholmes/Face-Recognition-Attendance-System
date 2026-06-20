# Hệ Thống Điểm Danh Bằng Nhận Diện Khuôn Mặt (Face Recognition Attendance System)

## Giới Thiệu
Hệ thống điểm danh tự động sử dụng công nghệ nhận diện khuôn mặt. Dự án áp dụng mô hình AI/Máy học để phát hiện, trích xuất đặc trưng (embedding) từ khuôn mặt và so khớp để xác nhận danh tính người dùng (sinh viên/nhân viên). Hệ thống được thiết kế theo kiến trúc Microservices linh hoạt và dễ dàng triển khai trọn gói bằng Docker Compose.

## Kiến Trúc và Các Thành Phần Của Dự Án

Dự án bao gồm các thành phần (services) sau, được đóng gói trong các Docker container độc lập:

1. **Frontend & Proxy Service (`app`)**:
   - **Công nghệ**: FastAPI + Jinja2 Templates.
   - **Chức năng**: Phục vụ giao diện web người dùng (UI) và đóng vai trò proxy server. Nhận request từ trình duyệt và chuyển tiếp an toàn (forward) đến Backend API và Face Service, giúp giải quyết triệt để các vấn đề về CORS và bảo mật frontend.
   - **Cổng nội bộ**: `5001`

2. **Backend API Core (`api`)**:
   - **Công nghệ**: FastAPI.
   - **Chức năng**: Xử lý logic nghiệp vụ chính như quản lý người dùng, ghi nhận lịch sử điểm danh, xác thực (Authentication) và quản lý cấu hình hệ thống. Có hỗ trợ cả giao tiếp qua Websocket.
   - **Hạ tầng tích hợp**: 
     - **Supabase**: Quản lý cơ sở dữ liệu quan hệ (PostgreSQL) và lưu trữ tệp tin (ảnh snapshot).
     - **Pinecone**: Cơ sở dữ liệu vector (Vector DB) hỗ trợ tìm kiếm và so khớp siêu tốc các vector đặc trưng khuôn mặt.
   - **Cổng nội bộ**: `8000`

3. **AI Face Recognition Service (`face` / client)**:
   - **Công nghệ**: Flask, OpenCV, MediaPipe, ONNXRuntime.
   - **Chức năng**: Chịu trách nhiệm hoàn toàn về Computer Vision. Xử lý hình ảnh/luồng camera theo thời gian thực, phát hiện khuôn mặt, trích xuất vector khuôn mặt và tương tác với Backend để nhận diện.
   - **Cổng nội bộ**: `5000`

4. **Background Task Queue (`worker` & `redis`)**:
   - **Công nghệ**: Celery (Worker) & Redis (Message Broker).
   - **Chức năng**: Chạy ngầm các tác vụ nặng, tốn thời gian hoặc cần xử lý bất đồng bộ, giúp cho API luôn phản hồi nhanh chóng.

5. **Reverse Proxy (`nginx`)**:
   - **Công nghệ**: Nginx.
   - **Chức năng**: Điều phối luồng traffic routing. Định tuyến các request HTTP thông thường vào Frontend và các request có tiền tố `/api/` hoặc `/ws` vào Backend API Core.
   - **Cổng công khai**: `80`

---

## Hướng Dẫn Khởi Chạy Dự Án (Docker Compose)

Hệ thống yêu cầu cài đặt sẵn **Docker** và **Docker Compose** trên máy của bạn.

### Bước 1: Cấu hình biến môi trường
Sao chép file `.env.example` thành file `.env` ở thư mục gốc của dự án:
```bash
cp .env.example .env
```
Mở file `.env` và điền đầy đủ các thông tin quan trọng như:
- Các biến kết nối **Supabase** (`SUPABASE_URL`, Key...)
- Biến kết nối **Pinecone** (`PINECONE_API_KEY`, Environment...)
- Bất kỳ cấu hình môi trường nào khác mà dự án yêu cầu.

### Bước 2: Build và Chạy hệ thống
Mở terminal tại thư mục gốc của dự án và chạy lệnh:
```bash
docker-compose up --build -d
```
*Lưu ý: Quá trình này có thể mất một chút thời gian cho lần chạy đầu tiên vì Docker cần tải base images và cài đặt các thư viện AI (OpenCV, ONNX, v.v.).*

### Bước 3: Sử dụng hệ thống
Sau khi các container báo trạng thái `Running` (hoặc `Up`), mở trình duyệt web và truy cập vào:
👉 **http://localhost** 

Traffic sẽ tự động được Nginx điều phối tới Frontend UI.

### Lệnh Docker Hữu Ích

- **Xem log toàn bộ hệ thống** để theo dõi lỗi hoặc quá trình nhận diện:
  ```bash
  docker-compose logs -f
  ```
- **Xem log của một service cụ thể** (VD: theo dõi module nhận diện khuôn mặt):
  ```bash
  docker-compose logs -f face
  ```
- **Tạm dừng hệ thống** (không xóa dữ liệu container):
  ```bash
  docker-compose stop
  ```
- **Tắt và xóa các container**:
  ```bash
  docker-compose down
  ```