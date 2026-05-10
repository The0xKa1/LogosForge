FROM python:3.11-slim

WORKDIR /app

# Use Chinese mirrors for Debian and pip
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

# System dependencies for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install all Python dependencies in one step
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Copy pre-downloaded embedding model
COPY models/models--BAAI--bge-large-zh-v1.5 /root/.cache/huggingface/hub/models--BAAI--bge-large-zh-v1.5

# Copy application code
COPY . .

# Persistent data directories
RUN mkdir -p /data/chroma_db /data/uploads /data/state

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
