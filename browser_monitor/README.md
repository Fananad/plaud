# Browser Monitor

Инструмент для мониторинга всех HTTP/HTTPS запросов браузера с помощью Playwright.

## Использование

Из корня проекта:

```bash
python browser_monitor/browser_monitor.py [url] [browser] [headless]
```

Или из папки browser_monitor:

```bash
cd browser_monitor
python browser_monitor.py [url] [browser] [headless]
```

## Примеры

```bash
# Базовое использование
python browser_monitor/browser_monitor.py https://example.com

# С выбором браузера
python browser_monitor/browser_monitor.py https://example.com chrome

# Headless режим
python browser_monitor/browser_monitor.py https://example.com chrome headless
```

## Файлы логов

Все логи сохраняются в папку `browser_monitor/logs` (путь считается автоматически, не зависит от текущей директории запуска):
- Текстовые логи: `logs/network_monitor_YYYYMMDD_HHMMSS.log`
- JSON данные: `logs/network_logs_YYYYMMDD_HHMMSS.json`

## Прерывание скрипта

Для остановки скрипта нажмите `Ctrl+C` или `Enter` в консоли. Скрипт корректно закроет браузер и сохранит все логи.
