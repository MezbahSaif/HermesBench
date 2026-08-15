#!/bin/bash
set -e

# Start cron daemon for background task scheduling
cron && crontab /app/crontab 2>/dev/null || true

# Setup logger with RotatingFileHandler
python /app/logger_config.py

# Main application loop: start Streamlit and worker in background, then wait
echo "Starting Streamlit Dashboard on port 8501..."
exec streamlit run app.py --server.port=8501 --server.headless=true &
STREAMLIT_PID=$!

# Start the background task worker
python /app/worker.py &
WORKER_PID=$!

echo "Dashboard PID: $STREAMLIT_PID"
echo "Worker PID: $WORKER_PID"

# Graceful shutdown handler
cleanup() {
    echo ""
    echo "Shutting down Dashboard..."
    
    if [ -n "${STREAMLIT_PID:-}" ]; then
        echo "Stopping Streamlit (PID: ${STREAMLIT_PID})..."
        kill "$STREAMLIT_PID" 2>/dev/null || true
        sleep 3
        # Force kill if still running
        if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
            kill -9 "$STREAMLIT_PID" 2>/dev/null || true
        fi
    fi
    
    if [ -n "${WORKER_PID:-}" ]; then
        echo "Stopping Worker (PID: ${WORKER_PID})..."
        kill "$WORKER_PID" 2>/dev/null || true
        sleep 3
        # Force kill if still running
        if kill -0 "$WORKER_PID" 2>/dev/null; then
            kill -9 "$WORKER_PID" 2>/dev/null || true
        fi
    fi
    
    echo "All processes stopped. Goodbye!"
}

trap cleanup SIGTERM SIGINT SIGHUP EXIT

# Keep the container running until a signal is received
wait -n $STREAMLIT_PID $WORKER_PID 2>/dev/null || exit 1
