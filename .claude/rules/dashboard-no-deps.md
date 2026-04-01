# Prospeqt Dashboard — No External Dependencies (HARD CONSTRAINT)

## The Rule

`server.py` must use **ONLY Python standard library** modules. No pip packages in production code.

## Allowed Imports (Production)

```python
import argparse
import hashlib
import hmac
import json
import os
import re
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
```

## Forbidden in Production

If you are about to write any of these — **STOP**:

```python
import requests        # Use urllib.request
from flask import ...  # Use http.server
import aiohttp         # Use threading + urllib
import httpx           # Use urllib.request
import jinja2          # Use string templates
import pydantic        # Use plain dicts + manual validation
import dotenv          # Use os.environ
```

## Dev-Only Dependencies (OK)

These are allowed in `tests/` and `qa/` only:

- `pytest` — test runner
- `playwright` — QA screenshots

## Why This Constraint Exists

- **Single-file deployment** to Render — no requirements.txt, no virtualenv in production
- **Zero setup** — `python server.py` works on any machine with Python 3.10+
- **No dependency drift** — no version conflicts, no security advisories for transitive deps
- Proven pattern: the original monolith (`client_dashboard.py`) runs in production with stdlib only
