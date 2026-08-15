# Streamlit Dashboard - Docker Deployment

A production-ready Streamlit dashboard deployed in a multi-stage Docker container with background task scheduling and structured logging.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Container                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Streamlit│  │  Worker  │  │   Cron   │  │
│  │  Server  │  │  Engine  │  │  Daemon  │  │
│  └─────┬────┘  └─────┬────┘  └──────────┘  │
│        │              │                      │
│  ┌─────▼──────────────▼──────────────────┐   │
│  │         Config (config.yaml)           │   │
│  │    Task Definitions + Logging Rules     │   │
│  └────────────────────────────────────────┘   │
│        │              │                      │
│  ┌─────▼────┐  ┌─────▼────┐                 │
│  │ Rotating  │  │ Data    │                 │
│  │ FileLog  │  │ Output  │                 │
│  │ Handlers │  │ Volumes │                 │
│  └──────────┘  └─────────┘                 │
└─────────────────────────────────────────────┘
         :8501                              :22
    ┌────▼────┐                          ┌────▼────┐
    │  Web    │                          │  SSH   │
    │ Browser │                          │ Access │
    └─────────┘                          └─────────┘
```

## Components

### Core Application (`app.py`)
- **Streamlit Dashboard** serving on port `8501`
- Interactive category filters (Sales, Marketing, Operations)
- Real-time metrics display with growth rate calculations
- Line charts and monthly breakdown bar charts

### Background Worker (`worker.py`)
- Fixed-interval task scheduler (e.g., hourly data refresh)
- Cron-style expression scheduler (standard 5-field cron syntax)
- Concurrent execution via asyncio
- Configurable through `config.yaml`

### Logging System (`logger_config.py`, entrypoint.sh)
- RotatingFileHandler with configurable max_bytes and backup_count
- Structured log format: `%Y-%m-%d %H:%M:%S | LEVEL | NAME | MESSAGE`
- Console + file dual output
- Graceful shutdown handling

## Quick Start

### Prerequisites
```bash
docker  # Docker Engine >= 20.10
docker-compose  # v2.x or docker compose plugin
```

### Build and Run
```bash
# Clone the repository
cd streamlit-dashboard/

# Build image (multi-stage, minimal runtime footprint)
docker build -t streamlit-dashboard .

# Start with default configuration
docker-compose up -d

# Access dashboard at http://localhost:8501
```

### Verify Health Check
```bash
curl -f http://localhost:8501/_stcore/health || echo "Service not ready"
```

## Usage

### Interactive Dashboard
1. Open `http://localhost:8501` in any modern browser
2. Select a category from the sidebar (Sales, Marketing, Operations)
3. View real-time metrics and charts

### Configuration (`config.yaml`)
- **tasks**: Define background tasks with schedule type (fixed_interval / cron), command path, and interval/expression
- **logging**: Configure log level, format, and RotatingFileHandler parameters
- **storage**: Set data/output directories and cache TTL

### Worker Scheduling
Background workers can be configured in `config.yaml`:

```yaml
tasks:
  - name: refresh_data
    schedule_type: fixed_interval
    interval_seconds: 3600
    command: python /app/refresh_metrics.py
    
  - name: clean_logs
    schedule_type: cron
    cron_expression: "0 */6 * * *"
    command: python /app/cleanup_logs.py
```

## CLI Commands

### Docker Compose Operations
```bash
# Start all services in background
docker-compose up -d

# Stop and remove containers (preserves volumes)
docker-compose down

# View logs
docker-compose logs -f dashboard

# Rebuild and restart
docker-compose up --build -d

# Execute commands inside running container
docker-compose exec dashboard bash

# Clean all data (volumes)
docker-compose down -v
```

### Direct Docker Commands
```bash
# Start from image without docker-compose
docker run -d -p 8501:8501 --name streamlit-dashboard streamlit-dashboard

# Run interactive shell inside container
docker exec -it streamlit-dashboard bash

# Stop and remove
docker stop streamlit-dashboard && docker rm streamlit-dashboard
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging verbosity (DEBUG/INFO/WARNING/ERROR) |
| `CONFIG_PATH` | /app/config.yaml | Path to configuration file |
| `LOG_DIR` | /data/logs | Directory for log rotation files |

## Configuration Guide

### Application Settings
Edit `/app/config.yaml`:
```yaml
application:
  name: "Streamlit Dashboard"
  port: 8501          # Must match exposed port in docker-compose.yml
  host: "0.0.0.0"     # Bind address (must be 0.0.0.0 for container access)

logging:
  level: INFO         # DEBUG | INFO | WARNING | ERROR
  format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  
  handlers:
    console: { enabled: true }
    file:
      enabled: true
      log_dir: /data/logs/app.log
      max_bytes: 10485760   # 10 MB per log file
      backup_count: 5       # Keep 5 rotated logs

storage:
  data_dir: "/app/data"
  output_dir: "/data/output"
  cache_enabled: true
```

### Task Definitions (config.yaml)
Background tasks support two scheduling modes:

#### Fixed-Interval Scheduling
```yaml
tasks:
  - name: hourly_refresh
    schedule_type: fixed_interval
    interval_seconds: 3600     # Every 1 hour
    enabled: true
    command: python /app/refresh_metrics.py
```

#### Cron Expression Scheduling  
Standard cron syntax (minute hour dom month dow):
```yaml
tasks:
  - name: log_rotation
    schedule_type: cron
    cron_expression: "0 */6 * * *"   # At minute 0 of every 6th hour
    enabled: true
    command: python /app/cleanup_logs.py
```

Supported cron fields: `*`, `*/N`, ranges (`1-5`), steps (`*/30`), lists (`,`).

## Volume Persistence

| Mount Path | Container Path | Purpose |
|------------|---------------|---------|
| `./data/logs` | `/data/logs` | Rotated application logs |
| `./data/output` | `/data/output` | Worker task output files |

Volumes persist across container restarts. The `/data` directory is owned by the non-root user (`appuser`).

## Troubleshooting

### Service Not Starting
```bash
# Check logs for startup errors
docker-compose logs dashboard

# Verify port 8501 is not in use locally
netstat -tlnp | grep :8501

# Rebuild if code changed
docker-compose up --build -d
```

### Container Crashes Immediately
- Check entrypoint script: `docker-compose exec dashboard bash` then review `/data/logs/app.log`
- Ensure all Python dependencies are installed (check builder stage logs)
- Verify volume mounts exist on the host filesystem

### Logs Not Rotating
1. Confirm `LOG_MAX_BYTES` and `LOG_BACKUP_COUNT` in environment or config
2. Check file permissions: volumes must be writable by `appuser`
3. Test manually inside container:
   ```bash
   docker-compose exec dashboard python -c "from logger_config import get_logger; l=get_logger(); l.info('test')"
   ```

### Dashboard Unreachable
- Ensure `docker-compose.yml` exposes port 8501 correctly
- Check firewall rules allow inbound traffic on 8501
- Verify health check is passing: `curl -f http://localhost:8501/_stcore/health`
- Streamlit startup takes ~30s; wait before checking

### Worker Not Running Tasks
- Open container shell and verify worker.py: `docker-compose exec dashboard python -c "import worker"`
- Check task definitions in config.yaml have `enabled: true`
- Review crontab: `crontab -l` inside the container
- Verify Python dependencies match requirements.txt

### Permission Denied Errors
```bash
# Fix ownership of data directories
docker-compose exec dashboard chown -R appuser:appuser /data

# Or add user mapping in docker-compose.yml
volumes:
  - ./data:/data    # ensures correct UID/GID on host
```

## Production Recommendations

1. **Secrets Management**: Use Docker secrets or environment variables for sensitive config (not stored in config.yaml)
2. **Resource Limits**: Add `deploy.resources` to docker-compose.yml for CPU/memory constraints
3. **Backup Strategy**: Regularly backup `/data/logs` and `/data/output` volumes
4. **Monitoring**: Configure health check alerts based on container restart count
5. **Security**: Run as non-root user (already configured), restrict port exposure

## License
MIT
