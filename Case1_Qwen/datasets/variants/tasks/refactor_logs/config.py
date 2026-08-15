"""Centralized configuration for the log summarizer."""


class Config:
    """Configuration constants for summarize().

    Attributes:
        sort_key: How to sort counted levels (e.g., 'count', '-count').
                  '-' prefix means descending; without it means ascending.
        line_split_index: Index of the level field in each log line.
                          Default is 1, meaning lines like "INFO message" -> INFO.
    """

    SORT_KEY = "-count"
    LINE_SPLIT_INDEX = 1


# Singleton instance for use across modules
CONFIG = Config()
