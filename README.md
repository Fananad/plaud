# Мониторинг сетевых запросов браузера и авторизация в Plaud.ai

Инструменты на Python для:
- Мониторинга всех HTTP/HTTPS запросов браузера с помощью Playwright
- Автоматической авторизации в Plaud.ai через Google SSO

## Установка

1. Убедитесь, что виртуальное окружение активировано:
```bash
source browser_monitor/venv/bin/activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Установите браузеры для Playwright:
```bash
playwright install chromium
```

## Структура проекта

```
plaud/
├── browser_monitor/      # Мониторинг сетевых запросов браузера
│   ├── browser_monitor.py
│   ├── logs/             # Логи (не коммитятся в git)
│   │   ├── network_monitor_*.log
│   │   └── network_logs_*.json
│   └── README.md
├── start.sh              # Запуск виртуалки и browser_monitor по абсолютному пути
└── README.md
```

## Быстрый старт

### Авторизация в Plaud.ai через Google SSO

Самый простой способ получить токен для работы с API Plaud.ai:

```bash
python google_sso_auth/google_sso_auth.py your.email@gmail.com your_password
```

После успешной авторизации токен будет сохранен в файл `google_sso_auth/plaud_token.json`.

Подробная документация: [google_sso_auth/GOOGLE_SSO_README.md](google_sso_auth/GOOGLE_SSO_README.md)

### Мониторинг сетевых запросов

```bash
python browser_monitor/browser_monitor.py https://example.com
# или
./start.sh https://example.com
```

Все логи сохраняются в папку `browser_monitor/logs/`.

Подробная документация: [browser_monitor/README.md](browser_monitor/README.md)

## Использование

### Базовое использование

Запустить скрипт с URL по умолчанию (example.com) в Chrome:
```bash
python browser_monitor.py
```

### Указать свой URL

```bash
python browser_monitor.py https://google.com
```

### Выбор браузера

Доступные браузеры: `chrome`, `chromium`, `webkit`, `firefox`

Использовать установленный Chrome на Mac:
```bash
python browser_monitor.py https://google.com chrome
```

Использовать Chromium (от Playwright):
```bash
python browser_monitor.py https://google.com chromium
```

Использовать WebKit (Safari-подобный):
```bash
python browser_monitor.py https://google.com webkit
```

### Headless режим (без GUI)

```bash
python browser_monitor.py https://google.com chrome headless
```

### Примеры

```bash
# Chrome с GUI (по умолчанию)
python browser_monitor.py https://example.com chrome

# Chrome в headless режиме
python browser_monitor.py https://example.com chrome headless

# WebKit с GUI
python browser_monitor.py https://example.com webkit
```

## Stealth режим

Скрипт автоматически включает stealth режим для скрытия признаков автоматизации:
- Удаляет флаг `navigator.webdriver`
- Добавляет реалистичный User-Agent
- Настраивает заголовки как у обычного браузера
- Отключает флаги автоматизации Chrome

Это помогает обойти блокировки сайтов, которые обнаруживают автоматизированные браузеры.

## Как это работает

1. Скрипт открывает браузер с stealth настройками
2. Перехватывает все сетевые запросы и ответы
3. Выводит информацию о каждом запросе в консоль в реальном времени
4. Сохраняет все логи в JSON файл после закрытия браузера

## Что мониторится

**Для каждого запроса сохраняется:**
- Метод запроса (GET, POST, PUT, DELETE и т.д.)
- Полный URL запроса
- Все заголовки запроса (включая authorization, cookie, content-type и др.)
- Все cookies из заголовка Cookie
- Полное тело запроса (POST данные, включая JSON)
- Тип ресурса (document, script, stylesheet, image и т.д.)

**Для каждого ответа сохраняется:**
- Статус код и текст статуса
- Все заголовки ответа (включая set-cookie, location и др.)
- Новые cookies из Set-Cookie заголовков
- Размер тела ответа
- Предпросмотр тела ответа (первые 1000 символов)

Все данные сохраняются в JSON файл для последующего использования в программах.

## Выходные файлы

После закрытия браузера создается JSON файл с именем `network_logs_YYYYMMDD_HHMMSS.json`, содержащий все собранные данные.

### Структура JSON файла

```json
{
  "requests": [
    {
      "timestamp": "2024-01-01T12:00:00",
      "type": "request",
      "method": "POST",
      "url": "https://example.com/api/login",
      "headers": {
        "content-type": "application/json",
        "cookie": "session=abc123",
        ...
      },
      "cookies": {
        "session": "abc123"
      },
      "post_data": "{\"username\": \"user\", \"password\": \"pass\"}",
      "resource_type": "xhr"
    }
  ],
  "responses": [
    {
      "timestamp": "2024-01-01T12:00:01",
      "type": "response",
      "url": "https://example.com/api/login",
      "status": 200,
      "headers": {
        "set-cookie": "token=xyz789; Path=/",
        ...
      },
      "cookies": {
        "token": "xyz789"
      },
      "body_size": 1024,
      "body_preview": "..."
    }
  ]
}
```

### Как использовать сохраненные данные

Все данные в JSON файле готовы для использования в вашем коде. Например, для повторения POST запроса:

```python
import json
import requests

# Загружаем сохраненные данные
with open('network_logs_20240101_120000.json', 'r') as f:
    logs = json.load(f)

# Находим нужный запрос (например, запрос на авторизацию)
auth_request = next(req for req in logs['requests'] 
                   if 'login' in req['url'].lower())

# Повторяем запрос с теми же параметрами
response = requests.post(
    url=auth_request['url'],
    headers=auth_request['headers'],
    data=auth_request['post_data'],
    cookies=auth_request['cookies']
)
```

Или используя сохраненные cookies из предыдущих ответов для последующих запросов.
