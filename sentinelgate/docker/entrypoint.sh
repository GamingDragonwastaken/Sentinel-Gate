#!/bin/bash
set -e

echo "Starting SentinelGate Backend API..."
exec uvicorn sentinelgate.api.server:app --host 0.0.0.0 --port 8501
