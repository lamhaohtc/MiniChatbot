FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY optibot ./optibot
COPY main.py ask.py ./

# Runs one sync (scrape -> diff -> upload delta) and exits 0.
# docker run -e OPENAI_API_KEY=sk-... <image>
CMD ["python", "main.py"]
