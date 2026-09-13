FROM python:3.12

# Set working directory
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Flask port
EXPOSE 5000

# Set environment variables (can be overridden at runtime)
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Use gunicorn for production (optional) – fallback to python if gunicorn not installed
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "1","--threads","4"]
