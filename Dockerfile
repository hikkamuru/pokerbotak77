FROM python:3.11-slim

WORKDIR /app

ENV DATA_DIR=/app/data

RUN mkdir -p /app/data && chmod 777 /app/data

RUN pip install --no-cache-dir \
    aiogram>=3.0.0 \
    aiohttp>=3.9.0 \
    aiosqlite==0.20.0 \
    pydantic-settings==2.7.0

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
