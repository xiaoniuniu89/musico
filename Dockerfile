# Use an official Python runtime as a parent image
FROM python:3.13-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies for psycopg and other tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir gunicorn whitenoise

# Copy project
COPY . /app/

# Make the start script executable
RUN chmod +x /app/start.sh

# Create a non-root user for security
RUN useradd -m musico && chown -R musico:musico /app
USER musico

# Collect static files (whitenoise will serve them)
RUN python manage.py collectstatic --noinput

# Run the application via start script
CMD ["/app/start.sh"]
