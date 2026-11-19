FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 FASTEMBED_CACHE_PATH=/opt/models
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
COPY main.py database.py rag.py company_pages.py ./
CMD ["sh", "-c", "exec uvicorn main:app --host ${BIND_HOST:-0.0.0.0} --port ${PORT:-8000}"]
