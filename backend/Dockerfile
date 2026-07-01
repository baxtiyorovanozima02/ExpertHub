@'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends `
    -o Acquire::Retries=5 `
    -o Acquire::http::Timeout=30 `
    gcc `
    libpq-dev `
    curl `
    && rm -rf /var/lib/apt/lists/*

COPY constraints.txt /constraints.txt
ENV PIP_CONSTRAINT=/constraints.txt

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir "setuptools<81" wheel

COPY requirements.txt .

RUN pip install --no-cache-dir `
    torch `
    torchvision `
    torchaudio `
    --index-url https://download.pytorch.org/whl/cpu `
    || echo "torch CPU install skipped (not in requirements)"

RUN pip install --no-cache-dir `
    --timeout=120 `
    --retries=5 `
    -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
'@ | Set-Content -Path "Dockerfile" -Encoding utf8NoBOM

Write-Host "Dockerfile muvaffaqiyatli qayta yozildi!" -ForegroundColor Green
Write-Host "Tekshirish uchun:" -ForegroundColor Yellow
type Dockerfile