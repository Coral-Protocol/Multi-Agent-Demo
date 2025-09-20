# Use minimal Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency files first for caching
COPY pyproject.toml /app/
COPY uv.lock /app/  # optional: if uv generates a lock file

# Install dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --non-interactive

# Copy the app code
COPY main.py /app/

# Expose port
EXPOSE 8000

# Run the app: uvicorn via uv
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
