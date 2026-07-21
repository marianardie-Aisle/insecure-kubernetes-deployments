# Start from Ubuntu
FROM ubuntu:20.04

# Avoid interactive dialog during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set SCRIPT_NAME for ingress-nginx
ENV SCRIPT_NAME=/app

# Install Python and pip (Docker CLI removed)
RUN apt-get update && \
    apt-get install -y python3 python3-pip curl apt-transport-https ca-certificates software-properties-common && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create /app directory and set as working directory
RUN mkdir /app
WORKDIR /app

# Add application and requirements.txt
COPY app.py /app/
COPY requirements.txt /app/
COPY templates /app/templates/

# Install Python packages from requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Create an uploads directory
RUN mkdir /uploads

# Install Flask
RUN python3 -m pip install Flask

# Create a non-root user and give ownership only to data and uploads directories
RUN useradd -m app && mkdir -p /app/data /app/data/uploads && chown -R app:app /app/data /uploads

# Run as the non-root user by default
USER app

CMD ["python3", "/app/app.py"]
