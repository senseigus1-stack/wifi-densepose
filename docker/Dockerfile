FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    git build-essential cmake libopenblas-dev libatlas-base-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p models && \
    python -c "import os; os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'; from transformers import AutoModelForImageClassification; AutoModelForImageClassification.from_pretrained('ruvnet/wifi-densepose-mmfi-pose', cache_dir='models')" || true

EXPOSE 5566/udp 3000

CMD ["python", "-m", "src.main"]