ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# Texterkennung für gescannte PDFs (tesseract mit Deutsch, Französisch, Italienisch; pdftoppm aus poppler)
RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-deu tesseract-ocr-data-fra tesseract-ocr-data-ita poppler-utils

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app
COPY config.yaml CHANGELOG.md /app/meta/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
# Ohne s6-overlay starten (init: false): Python läuft direkt als Hauptprozess
ENTRYPOINT []
CMD ["/run.sh"]
