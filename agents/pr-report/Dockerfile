FROM python:3.13-slim

WORKDIR /app

# Install system tools
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN pip install --upgrade pip && pip install uv

# Copy project files including pyproject.toml and uv.lock (if exists)
COPY . .

# Create virtual environment and sync dependencies
RUN uv venv && uv pip install --upgrade pip && uv sync --no-dev

# Expose necessary ports
EXPOSE 3001 5555

# Run app with virtual environment
CMD ["uv", "run", "python", "main.py"]
