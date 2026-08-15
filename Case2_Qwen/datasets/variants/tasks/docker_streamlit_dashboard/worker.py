#!/usr/bin/env python3
"""Background task worker with scheduling support.

Supports both fixed-interval and cron-style scheduling for background tasks
defined in config.yaml. Uses a daemon loop to process scheduled tasks.

Usage:
    python worker.py [--config CONFIG_PATH] [--interval SECONDS]
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def setup_logging(config_path=None):
    """Configure structured logging with RotatingFileHandler."""
    logger = logging.getLogger("worker")

    if logger.handlers:
        return logger

    # Set level from environment or default to INFO
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with RotatingFileHandler for structured log rotation
    log_dir = os.environ.get("LOG_DIR", "/data/logs")
    os.makedirs(log_dir, exist_ok=True)

    file_path = os.path.join(log_dir, "app.log")

    max_bytes = int(os.environ.get("LOG_MAX_BYTES", "10485760"))  # 10 MB default
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

    file_handler = logging.handlers.RotatingFileHandler(
        filename=file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def load_config(config_path):
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        logging.getLogger("worker").warning(
            f"Config file not found at {config_path}, using defaults")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


class FixedIntervalScheduler:
    """Schedule tasks at fixed intervals."""

    def __init__(self, interval_seconds, task_command):
        self.interval = timedelta(seconds=interval_seconds)
        self.task_command = task_command
        self.last_run = None

    async def run(self):
        logger.info(f"FixedIntervalScheduler started (every {self.interval})")
        while True:
            await asyncio.sleep(1)
            now = datetime.now()
            if self.last_run is None or now >= self.last_run + self.interval:
                self.last_run = now
                try:
                    logger.info(f"Running task at fixed interval: {self.task_command}")
                    result = await asyncio.create_subprocess_shell(
                        self.task_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await result.wait()
                    if result.returncode != 0:
                        logger.error(f"Task failed with code {result.returncode}")
                except Exception as e:
                    logger.exception(f"Scheduled task error: {e}")


class CronScheduler:
    """Schedule tasks using cron-style expressions."""

    @staticmethod
    def parse_cron_field(field, min_val, max_val):
        """Parse a single cron field and return matching values.

        Supports: *, */N, ranges (1-5), steps (*2 or 0-30/10),
                  lists (1,3,5), single integers.
        Returns a list of integers within [min_val, max_val].
        """
        if field == "*":
            return list(range(min_val, max_val + 1))

        # List: "1,3,5"
        if "," in field:
            values = []
            for part in field.split(","):
                values.extend(CronScheduler.parse_cron_field(part.strip(), min_val, max_val))
            return sorted(set(values))

        # Range with step: "0-6/2"
        parts = field.split("/")
        if len(parts) == 1:
            base_str = field
            step = None
        else:
            base_str = parts[0]
            try:
                step = int(parts[1])
            except ValueError:
                return list(range(min_val, max_val + 1))

        # Range with step or without: "2-6/3" or "2-6"
        if "-" in base_str and not base_str.startswith("*"):
            range_parts = base_str.split("-")
            start = int(range_parts[0])
            end = int(range_parts[1])

            values = list(range(start, end + 1))

            # Apply step
            if step:
                values = [v for v in values if v % step == start % step]

            return sorted(set(v for v in values if min_val <= v <= max_val))

        # Single value or * with step: "*" or "*/2"
        try:
            val = int(field)
            if step is not None and step > 0:
                values = []
                for i in range(min_val, max_val + 1):
                    if (i - min_val) % step == 0:
                        values.append(i)
                return sorted(values)
            return [val]
        except ValueError:
            # Fallback: return full range
            return list(range(min_val, max_val + 1))

    @staticmethod
    def matches_now(cron_expr):
        """Check if the current time matches a simplified cron expression.

        Supports minute hour dom month dow fields with *, */N, ranges, steps, and lists.
        Only supports 5-field expressions (minute hour day-of-month month day-of-week).
        """
        parts = cron_expr.strip().split()

        if len(parts) < 4:
            return False

        # Extract numeric values for minute, hour, dom, month
        try:
            minute_val = int(parts[0])
            hour_val = int(parts[1])
            dom_val = int(parts[2])
            month_val = int(parts[3])
        except ValueError:
            return False

        now_minute = datetime.now().minute
        now_hour = datetime.now().hour
        today_dom = datetime.now().day
        today_month = datetime.now().month

        minute_match = now_minute in CronScheduler.parse_cron_field(minute_val, 0, 59)
        hour_match = now_hour in CronScheduler.parse_cron_field(hour_val, 0, 23)
        dom_match = today_dom in CronScheduler.parse_cron_field(dom_val, 1, 31)
        month_match = today_month in CronScheduler.parse_cron_field(month_val, 1, 12)

        return (minute_match and hour_match and dom_match and month_match)

    async def run(self):
        logger.info(f"CronScheduler started: checking every 30 seconds")
        while True:
            await asyncio.sleep(30)

            for task_config in tasks:
                if task_config.get("schedule_type") == "cron" and task_config["enabled"]:
                    cron_expr = task_config.get("cron_expression", "* * * * *")
                    if self.matches_now(cron_expr):
                        command = task_config["command"]
                        try:
                            logger.info(f"Running cron task: {task_config['name']} ({command})")
                            result = await asyncio.create_subprocess_shell(
                                command,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            await result.wait()
                            if result.returncode != 0:
                                logger.error(f"Task {task_config['name']} failed with code {result.returncode}")
                        except Exception as e:
                            logger.exception(f"Cron task error for {task_config['name']}: {e}")


async def main():
    """Main worker loop."""
    global tasks

    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    try:
        if not os.path.exists(config_path):
            logging.getLogger("worker").warning(
                f"Config file not found at {config_path}, using defaults")
            return

        config = load_config(config_path)

        app_config = config.get("application", {})
        logging_config = config.get("logging", {})

        log_dir = "/data/logs"
        os.makedirs(log_dir, exist_ok=True)

        # Setup file handler if configured in YAML
        handlers = logging_config.get("handlers", {})
        if handlers and handlers.get("file", {}).get("enabled"):
            max_bytes = 10 * 1024 * 1024
            backup_count = config.get("logging", {}).get(
                "handlers", {}).get("file", {}).get("backup_count", 5)

            file_handler = logging.handlers.RotatingFileHandler(
                log_dir + "/app.log",
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            formatter = logging.Formatter(logging_config["handlers"]["file"].get(
                "formatter", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
            file_handler.setFormatter(formatter)

            # Register with the worker logger (not yet created; add to all loggers)
            for lg in logging.root.handlers[:]:
                if isinstance(lg, logging.StreamHandler):  # avoid adding twice
                    pass
            try:
                logger = logging.getLogger("worker")
                if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
                    logger.addHandler(file_handler)
            except Exception:
                pass

        tasks = config.get("tasks", []) or []

        # Print task summary to console
        for task_config in tasks:
            task_name = task_config.get("name", "unnamed")
            schedule_type = task_config["schedule_type"]
            command = task_config["command"]

            logger.info(f"Task '{task_name}': {schedule_type} - {command}")

    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return

    # Run both schedulers concurrently
    schedulers = []

    for task_config in tasks:
        if task_config.get("schedule_type") == "fixed_interval":
            scheduler = FixedIntervalScheduler(
                interval_seconds=task_config["interval_seconds"],
                task_command=task_config["command"]
            )
            schedulers.append(scheduler.run())

    cron_schedulers = []
    for task_config in tasks:
        if task_config.get("schedule_type") == "cron":
            scheduler = CronScheduler()
            cron_schedulers.append(scheduler.run())

    await asyncio.gather(*schedulers, *cron_schedulers)


if __name__ == "__main__":
    asyncio.run(main())
