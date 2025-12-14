#!/usr/bin/env bash
set -euo pipefail

# Абсолютные пути на основе расположения этого скрипта

MONITOR_DIR="/Users/gosharodionov/develop/plaud/browser_monitor"
VENV_DIR="$MONITOR_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python3"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Не найдено виртуальное окружение по пути: $PYTHON_BIN"
  echo "Создайте его или скорректируйте путь в start.sh"
  exit 1
fi

# Активируем окружение и запускаем монитор с абсолютным путём
source "$VENV_DIR/bin/activate"
exec "$PYTHON_BIN" "$MONITOR_DIR/browser_monitor.py" "$@"
