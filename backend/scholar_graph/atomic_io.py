"""Bounded retries for Windows sharing/access locks, preserving atomic operations."""

import os
import time

BACKOFF = (0.025, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6)


def windows_retry(operation):
    for attempt in range(len(BACKOFF) + 1):
        try:
            return operation()
        except OSError as error:
            if os.name != "nt" or getattr(error, "winerror", None) not in {5, 32, 33} or attempt == len(BACKOFF):
                raise
            # The owner can close its handle during this bounded wait. Permanent ACL errors
            # still fail; do not copy a partly published directory or overwrite old records.
            time.sleep(BACKOFF[attempt])
