FROM python:3.12.8
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["sh", "-c", "python -m unittest discover -v -s ./tests && python ./main.py"]
