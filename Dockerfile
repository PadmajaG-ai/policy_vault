FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Scans call Gemini several times: allow long requests (gunicorn's default is 30s)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 main:app
