FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip

# Keep the image build simple; GPU-specific torch install should be handled
# by the runtime environment if Docker GPU passthrough is needed.
RUN pip install --no-cache-dir -r /app/requirements.txt || true

COPY . /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
