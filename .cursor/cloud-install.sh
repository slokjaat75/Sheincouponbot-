#!/usr/bin/env bash
set -euo pipefail

cd /workspace

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  php-cli \
  php-curl \
  php-mbstring \
  php-xml \
  python3-venv

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

php -l Telegram.php

.venv/bin/python - <<'PY'
import telegram
import aiohttp
import requests
print("python-telegram-bot", telegram.__version__)
print("requests", requests.__version__)
print("aiohttp", aiohttp.__version__)
PY
