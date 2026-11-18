FROM python:3.11-slim

# Thiết lập các biến môi trường cho Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt các gói thư viện Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . /app/

# Đặt thư mục làm việc mặc định vào web để chạy manage.py
WORKDIR /app/web

# Chạy migrate và khởi động máy chủ Django
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
