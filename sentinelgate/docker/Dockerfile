FROM python:3.11-slim-bullseye

# Install necessary system dependencies (like curl to download lobster)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the requirements and install them
COPY sentinelgate/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY sentinelgate/ ./sentinelgate/

# The setup_lobster script will download the right lobstertrap binary for this architecture (linux-amd64 or arm64 fallback)
RUN python sentinelgate/setup_lobster.py

# Ensure entrypoint is executable
COPY sentinelgate/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose Streamlit port
EXPOSE 8501

# Start the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
