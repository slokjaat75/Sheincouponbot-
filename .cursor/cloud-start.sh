#!/usr/bin/env bash
set -euo pipefail

cd /workspace

if [[ -f index.php ]]; then
  exec php index.php
fi

if [[ -f main.py ]]; then
  exec /workspace/.venv/bin/python main.py
fi

echo "No bot entrypoint (index.php or main.py) found; dependencies are installed."
echo "Set TELEGRAM_BOT_TOKEN and add main.py or index.php to run the bot."
exit 0
