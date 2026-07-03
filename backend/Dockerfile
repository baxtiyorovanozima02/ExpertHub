# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    -o Acquire::Retries=5 \
    -o Acquire::http::Timeout=30 \
    curl \
    xz-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz \
    && tar -xf /tmp/ffmpeg.tar.xz -C /tmp \
    && mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && rm -rf /tmp/ffmpeg*

COPY constraints.txt /constraints.txt
ENV PIP_CONSTRAINT=/constraints.txt


RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "setuptools<81" wheel

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    torch==2.4.1 \
    torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout=120 \
    --retries=5 \
    -r requirements.txt

ENV HF_HOME=/root/.cache/huggingface

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]