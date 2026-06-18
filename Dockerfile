FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml .

COPY app/ ./app/

RUN pip install --no-cache-dir .

RUN useradd -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 3000

ENTRYPOINT ["caching-proxy"]

CMD ["--port", "3000", "--origin", "https://dummyjson.com"]