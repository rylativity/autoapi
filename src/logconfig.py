import logging
import os

## Shared logic across AutoAPI for accessing and using Logger instance

DEBUG = os.environ.get("DEBUG")
if DEBUG:
    DEBUG = True
else:
    DEBUG = False

if __name__ == "__main__":
    log = logging.getLogger(__name__)
else:
    log = logging.getLogger("uvicorn")

if DEBUG:
    log.setLevel(logging.DEBUG)
    log.warn("DEBUG LOGGING ENABLED")
else:
    log.setLevel(logging.INFO)
