FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends \
       libegl1 \
       libgles2 \
       libgl1 \
       libglib2.0-0 \
       && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip uninstall opencv-contrib-python --y
RUN pip uninstall opencv-python --y
RUN pip install --no-cache-dir opencv-python-headless

COPY . .
RUN [ -f .env ] || cp .env.example .env