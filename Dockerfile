FROM python:3.12.8
WORKDIR /app
COPY . .
# tesseract for ocr for pdfs
RUN apt-get update && apt-get install -y tesseract-ocr
RUN pip install --upgrade pip
RUN pip install -r requirements.txt