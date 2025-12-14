#!/usr/bin/env python3
"""
Скрипт для мониторинга всех HTTP/HTTPS запросов браузера
Использует Playwright для автоматизации браузера и перехвата сетевых запросов
"""

import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import List, Dict, Any

# Директория для логов (лежит рядом со скриптом, путь абсолютный)
LOGS_DIR = (Path(__file__).resolve().parent / "logs").resolve()
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class RequestMonitor:
    """Класс для мониторинга и логирования сетевых запросов"""
    
    def __init__(self, log_file: str = None):
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []
        self.log_file = log_file
        if self.log_file:
            # Очищаем файл при создании
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"Network Monitor Log - Started at {datetime.now().isoformat()}\n")
                f.write("="*80 + "\n\n")
    
    def _log(self, message: str):
        """Выводит сообщение и в консоль, и в файл"""
        print(message, end='')
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(message)
            except Exception as e:
                print(f"\n⚠️  Ошибка записи в файл логов: {e}")
    
    def log_request(self, request):
        """Логирует исходящий запрос со всеми деталями"""
        # Получаем cookies из заголовков
        cookies_str = request.headers.get('cookie', '')
        cookies_dict = {}
        if cookies_str:
            for cookie in cookies_str.split('; '):
                if '=' in cookie:
                    key, value = cookie.split('=', 1)
                    cookies_dict[key] = value
        
        request_data = {
            'timestamp': datetime.now().isoformat(),
            'type': 'request',
            'method': request.method,
            'url': request.url,
            'headers': request.headers,
            'cookies': cookies_dict,
            'post_data': request.post_data,
            'resource_type': request.resource_type,
        }
        self.requests.append(request_data)
        
        log_lines = [
            f"\n{'='*80}\n",
            f"🔵 REQUEST [{request.method}] {request.url}\n",
            f"   Resource Type: {request.resource_type}\n",
        ]
        
        # Выводим важные заголовки
        important_headers = ['authorization', 'cookie', 'content-type', 'referer', 'user-agent', 'x-csrf-token']
        log_lines.append("\n   📋 Headers:\n")
        for header, value in request.headers.items():
            if header.lower() in important_headers or header.lower().startswith('x-'):
                # Обрезаем длинные значения для вывода
                display_value = value if len(value) < 200 else value[:200] + "..."
                log_lines.append(f"      {header}: {display_value}\n")
        
        # Выводим cookies отдельно
        if cookies_dict:
            log_lines.append("\n   🍪 Cookies:\n")
            for key, value in cookies_dict.items():
                display_value = value if len(value) < 100 else value[:100] + "..."
                log_lines.append(f"      {key}: {display_value}\n")
        
        # Выводим тело запроса полностью
        if request.post_data:
            log_lines.append("\n   📦 Request Body:\n")
            try:
                # Пытаемся распарсить как JSON для красивого вывода
                import json as json_module
                body_json = json_module.loads(request.post_data)
                log_lines.append(f"      {json_module.dumps(body_json, indent=6)}\n")
            except:
                # Если не JSON, выводим как есть (полностью)
                log_lines.append(f"      {request.post_data}\n")
        
        # Выводим все строки
        for line in log_lines:
            self._log(line)
    
    def log_response(self, response):
        """Логирует входящий ответ со всеми деталями"""
        try:
            status = response.status
            status_text = response.status_text
            headers = response.headers
            
            # Извлекаем cookies из заголовка Set-Cookie
            cookies_from_response = {}
            # Ищем Set-Cookie в разных регистрах
            set_cookie_key = None
            for key in headers.keys():
                if key.lower() == 'set-cookie':
                    set_cookie_key = key
                    break
            
            if set_cookie_key:
                set_cookie_headers = headers[set_cookie_key]
                if set_cookie_headers:
                    # Set-Cookie может быть списком или строкой
                    cookie_list = set_cookie_headers if isinstance(set_cookie_headers, list) else [set_cookie_headers]
                    for cookie_str in cookie_list:
                        if cookie_str:
                            # Берем только первую часть до точки с запятой (name=value)
                            cookie_parts = cookie_str.split(';')[0].strip()
                            if '=' in cookie_parts:
                                key, value = cookie_parts.split('=', 1)
                                cookies_from_response[key] = value
            
            # Пытаемся получить тело ответа
            response_body = None
            response_size = None
            try:
                if response.ok:
                    response_body = response.body()
                    response_size = len(response_body)
                    # Ограничиваем размер для сохранения (первые 100KB)
                    if response_size > 100 * 1024:
                        response_body = response_body[:100 * 1024]
            except:
                pass
            
            response_data = {
                'timestamp': datetime.now().isoformat(),
                'type': 'response',
                'url': response.url,
                'status': status,
                'status_text': status_text,
                'headers': headers,
                'cookies': cookies_from_response,
                'body_size': response_size,
                'body_preview': response_body.decode('utf-8', errors='ignore')[:1000] if response_body else None,
            }
            
            self.responses.append(response_data)
            
            status_emoji = "🟢" if 200 <= status < 300 else "🟡" if 300 <= status < 400 else "🔴"
            log_lines = [
                f"\n{status_emoji} RESPONSE [{status} {status_text}] {response.url}\n",
            ]
            
            # Выводим размер ответа
            if response_size:
                size_kb = response_size / 1024
                log_lines.append(f"   Size: {size_kb:.2f} KB\n")
            
            # Выводим важные заголовки ответа
            important_response_headers = ['set-cookie', 'location', 'authorization', 'content-type']
            has_important = any(h.lower() in [ih.lower() for ih in important_response_headers] for h in headers.keys())
            if has_important:
                log_lines.append("\n   📋 Important Headers:\n")
                for header, value in headers.items():
                    if header.lower() in important_response_headers:
                        display_value = value if len(str(value)) < 200 else str(value)[:200] + "..."
                        log_lines.append(f"      {header}: {display_value}\n")
            
            # Выводим новые cookies
            if cookies_from_response:
                log_lines.append("\n   🍪 New Cookies:\n")
                for key, value in cookies_from_response.items():
                    display_value = value if len(value) < 100 else value[:100] + "..."
                    log_lines.append(f"      {key}: {display_value}\n")
            
            # Выводим все строки
            for line in log_lines:
                self._log(line)
                
        except Exception as e:
            error_msg = f"\n⚠️  Error logging response: {e}\n"
            self._log(error_msg)
    
    def log_failed_request(self, request):
        """Логирует неудачный запрос"""
        log_lines = [
            f"\n❌ FAILED REQUEST: {request.url}\n",
            f"   Method: {request.method}\n",
        ]
        for line in log_lines:
            self._log(line)
    
    def save_to_file(self, filename: str = None):
        """Сохраняет все логи в JSON файл"""
        if filename is None:
            filename = str(LOGS_DIR / f"network_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        else:
            # Если путь относительный, добавляем папку logs
            log_path = Path(filename)
            if not log_path.is_absolute():
                filename = str(LOGS_DIR / filename)
        
        all_logs = {
            'requests': self.requests,
            'responses': self.responses,
            'summary': {
                'total_requests': len(self.requests),
                'total_responses': len(self.responses),
            }
        }
        
        filename = str(Path(filename).resolve())
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_logs, f, indent=2, ensure_ascii=False)
        
        self._log(f"\n📄 Логи сохранены в файл: {filename}\n")
        return filename


async def monitor_browser(url: str = "https://example.com", browser_type: str = "chrome", 
                          headless: bool = False, save_logs: bool = True, log_file: str = None):
    """
    Открывает браузер и мониторит все сетевые запросы для повторения их программно
    
    Args:
        url: URL для открытия в браузере
        browser_type: Тип браузера ('chrome', 'chromium', 'webkit', 'firefox')
        headless: Запускать браузер в headless режиме (без GUI)
        save_logs: Сохранять ли логи в JSON файл (все данные для повторения запросов)
        log_file: Путь к файлу для текстовых логов (если None, создается автоматически)
    """
    # Создаем имя файла для текстовых логов, если не указано
    if log_file is None:
        log_file = LOGS_DIR / f"network_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    else:
        # Если путь относительный, добавляем папку logs
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_file = LOGS_DIR / log_file
    
    log_file = str(Path(log_file).resolve())
    
    monitor = RequestMonitor(log_file=log_file)
    browser = None
    shutdown_event = asyncio.Event()
    
    # Обработчик сигналов для корректного завершения
    def signal_handler(sig, frame):
        print("\n\n🛑 Получен сигнал прерывания (Ctrl+C)...")
        shutdown_event.set()
    
    # Устанавливаем обработчики сигналов
    if sys.platform != "win32":
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async with async_playwright() as p:
        info_lines = [
            f"🚀 Запуск браузера...\n",
            f"🌍 Браузер: {browser_type.capitalize()}\n",
            f"📝 Режим: {'Headless' if headless else 'С GUI'}\n",
            f"🌐 URL: {url}\n",
            f"📂 Папка логов: {LOGS_DIR}\n",
            f"📄 Логи: {log_file}\n",
        ]
        for line in info_lines:
            monitor._log(line)
        
        # Запускаем выбранный браузер с stealth настройками
        browser_type = browser_type.lower()
        launch_options = {
            "headless": headless,
        }
        
        # Создаем контекст с реалистичными настройками (stealth режим)
        # Используем реальный user agent Chrome для macOS
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        context_options = {
            "user_agent": user_agent,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "permissions": ["geolocation"],
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
            "ignore_https_errors": False,
        }
        
        # Создаем браузер с stealth настройками
        if browser_type == "chrome":
            # Используем установленный Chrome на Mac с stealth флагами
            launch_options.update({
                "channel": "chrome",
                "args": [
                    "--disable-blink-features=AutomationControlled",
                ]
            })
            browser = await p.chromium.launch(**launch_options)
        elif browser_type == "chromium":
            launch_options["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
            browser = await p.chromium.launch(**launch_options)
        elif browser_type == "webkit":
            browser = await p.webkit.launch(headless=headless)
        elif browser_type == "firefox":
            browser = await p.firefox.launch(headless=headless)
        else:
            print(f"⚠️  Неизвестный тип браузера '{browser_type}', используется Chrome")
            launch_options.update({
                "channel": "chrome",
                "args": [
                    "--disable-blink-features=AutomationControlled",
                ]
            })
            browser = await p.chromium.launch(**launch_options)
        
        # Создаем контекст с stealth настройками
        context = await browser.new_context(**context_options)
        
        # Убираем признаки автоматизации через JavaScript
        page = await context.new_page()
        
        # Скрываем webdriver флаг и другие признаки автоматизации
        await page.add_init_script("""
            // Скрываем webdriver флаг
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Убираем плагины автоматизации
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Добавляем Chrome в window
            window.chrome = {
                runtime: {}
            };
            
            // Исправляем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Скрываем наличие автоматизации в navigator
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        # Устанавливаем обработчики для перехвата запросов и ответов
        page.on("request", monitor.log_request)
        page.on("response", monitor.log_response)
        page.on("requestfailed", monitor.log_failed_request)
        
        try:
            monitor._log(f"\n⏳ Загрузка страницы...\n")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            monitor._log(f"\n✅ Страница загружена!\n")
            monitor._log(f"\n💡 Браузер открыт. Вы можете взаимодействовать с ним.\n")
            monitor._log(f"💡 Все сетевые запросы будут логироваться здесь и в файл {log_file}\n")
            monitor._log(f"💡 Нажмите Enter в консоли или Ctrl+C, чтобы закрыть браузер...\n\n")
            
            # Ждем либо ввода пользователя, либо сигнала завершения
            async def wait_for_input():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, input)
                shutdown_event.set()
            
            async def wait_for_shutdown():
                await shutdown_event.wait()
            
            # Запускаем оба таска и ждем любого из них
            await asyncio.wait([
                asyncio.create_task(wait_for_input()),
                asyncio.create_task(wait_for_shutdown())
            ], return_when=asyncio.FIRST_COMPLETED)
            
        except PlaywrightTimeoutError:
            monitor._log(f"\n⏱️  Таймаут при загрузке страницы, но браузер остается открытым\n")
            monitor._log(f"💡 Нажмите Enter в консоли или Ctrl+C, чтобы закрыть браузер...\n\n")
            async def wait_for_input():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, input)
                shutdown_event.set()
            
            async def wait_for_shutdown():
                await shutdown_event.wait()
            
            await asyncio.wait([
                asyncio.create_task(wait_for_input()),
                asyncio.create_task(wait_for_shutdown())
            ], return_when=asyncio.FIRST_COMPLETED)
            
        except KeyboardInterrupt:
            monitor._log(f"\n\n🛑 Прерывание пользователем (Ctrl+C)...\n")
        except Exception as e:
            monitor._log(f"\n❌ Ошибка: {e}\n")
        
        finally:
            monitor._log(f"\n🛑 Закрытие браузера...\n")
            try:
                if browser:
                    await browser.close()
            except Exception as e:
                monitor._log(f"⚠️  Ошибка при закрытии браузера: {e}\n")
            
            # Сохраняем логи если нужно
            json_file = None
            if save_logs:
                json_file = monitor.save_to_file()
            
            # Выводим итоговую статистику
            stats_lines = [
                f"\n📊 Статистика:\n",
                f"   Всего запросов: {len(monitor.requests)}\n",
                f"   Всего ответов: {len(monitor.responses)}\n",
            ]
            
            # Группировка по типам ресурсов
            resource_types = {}
            for req in monitor.requests:
                rt = req.get('resource_type', 'other')
                resource_types[rt] = resource_types.get(rt, 0) + 1
            
            if resource_types:
                stats_lines.append(f"\n📦 Запросы по типам ресурсов:\n")
                for rt, count in sorted(resource_types.items(), key=lambda x: x[1], reverse=True):
                    stats_lines.append(f"   {rt}: {count}\n")
            
            stats_lines.append(f"\n📄 Текстовые логи сохранены в: {log_file}\n")
            if save_logs and json_file:
                stats_lines.append(f"📄 JSON данные сохранены в: {json_file}\n")
            
            for line in stats_lines:
                monitor._log(line)


if __name__ == "__main__":
    import sys
    
    # Парсинг аргументов командной строки
    url = "https://example.com"
    browser_type = "chrome"  # По умолчанию используем Chrome
    headless = False
    
    # Использование: python browser_monitor.py [url] [browser] [headless]
    # Браузеры: chrome, chromium, webkit, firefox
    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        arg2 = sys.argv[2].lower()
        if arg2 in ['chrome', 'chromium', 'webkit', 'firefox']:
            browser_type = arg2
        elif arg2 == 'headless':
            headless = True
    if len(sys.argv) > 3:
        if sys.argv[3].lower() == 'headless':
            headless = True
    
    print("="*80)
    print("🌐 Мониторинг сетевых запросов браузера")
    print("💡 Все данные запросов (headers, cookies, body) будут сохранены в JSON")
    print("="*80)
    
    # Запуск
    asyncio.run(monitor_browser(
        url=url, 
        browser_type=browser_type, 
        headless=headless, 
        save_logs=True
    ))
