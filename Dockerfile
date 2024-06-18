FROM python:3.12.4

WORKDIR /app

COPY . .

# Install tesseract for for pdf ocr.
RUN apt-get update && apt-get install -y tesseract-ocr

# Install python deps.
RUN pip install -r requirements.txt
