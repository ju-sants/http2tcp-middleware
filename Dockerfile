FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only requirements first to leverage layer cache
COPY requirements.txt /app/

# Install dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
	pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Start the application
CMD ["python", "main.py"]
