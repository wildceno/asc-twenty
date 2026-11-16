FROM python:3.12-slim
# LibreOffice (MPL-2.0) yalnız PDF'e çevirmek için; yazı tipleri Türkçe karakterleri kapsar (DejaVu, Liberation)
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-impress \
      fonts-dejavu fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY belge_servisi ./belge_servisi
COPY testler ./testler
ENV PYTHONUNBUFFERED=1 HOME=/tmp
CMD ["python3", "-m", "belge_servisi"]
