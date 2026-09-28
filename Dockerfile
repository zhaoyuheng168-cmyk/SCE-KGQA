FROM python:3.10-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
WORKDIR /workspace
COPY requirements-core.lock .
RUN pip install --no-cache-dir -r requirements-core.lock
COPY . .
CMD ["python", "tools/validate_release.py"]
