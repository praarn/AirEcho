FROM python:3.12-slim

# tesseract for peak-flow OCR; libgl/glib for pillow + torch runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

WORKDIR /app

COPY pyproject.toml ./
# Install the CPU-only torch build first so sentence-transformers doesn't pull
# the multi-GB CUDA stack it can't use in this container.
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -e ".[dev]"

COPY . .

# pre-download the sentence-transformers model so first RAG call isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
