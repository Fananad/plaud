#!/usr/bin/env python3
"""
Клиент для работы с Plaud API
Позволяет получать списки директорий и записей, экспортировать файлы
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    sys.stderr.write(
        "Не найден модуль requests. Установите зависимости: pip install -r requirements.txt\n"
    )
    raise

TOKEN_FILE = Path(__file__).parent / ".token"


def load_token() -> str:
    """Читает токен из файла .token рядом со скриптом."""
    if not TOKEN_FILE.exists():
        sys.stderr.write(f"Файл с токеном не найден: {TOKEN_FILE}\n")
        sys.stderr.write("Создайте файл .token и поместите туда токен (с или без префикса 'bearer').\n")
        sys.exit(1)
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        sys.stderr.write(f"Файл {TOKEN_FILE} пуст. Поместите токен.\n")
        sys.exit(1)
    # Убираем префикс "bearer " если он есть (регистронезависимо)
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def build_session(bearer: str):
    """Создает сессию requests с необходимыми заголовками."""
    session = requests.Session()

    session.headers.update(
        {
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "accept-language": "en-US,en;q=0.9",
            "app-platform": "web",
            "app-language": "en",
            "authorization": f"bearer {bearer}",
        }
    )

    return session


def get_file_summary(session, file_id: str):
    """Получает summary файла для экспорта."""
    # Пробуем разные варианты endpoint'ов
    endpoints = [
        f"https://api.plaud.ai/file/{file_id}/summary",
        f"https://api.plaud.ai/file/{file_id}",
        f"https://api.plaud.ai/ai/query_source?file-id={file_id}",
    ]
    
    for endpoint in endpoints:
        try:
            headers = {"file-id": file_id}
            response = session.get(endpoint, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            continue
    return None


def export_file_to_md(session, file_id: str, filename: str, file_info: dict = None) -> str:
    """Экспортирует файл в формат Markdown."""
    # Пробуем разные варианты endpoint'ов для экспорта
    export_endpoints = [
        f"https://api.plaud.ai/file/{file_id}/export?format=md",
        f"https://api.plaud.ai/file/{file_id}/export?format=markdown",
        f"https://api.plaud.ai/file/{file_id}/summary/export?format=md",
        f"https://api.plaud.ai/summary/export?fileID={file_id}&format=md",
    ]
    
    for endpoint in export_endpoints:
        try:
            response = session.get(endpoint, timeout=30)
            if response.status_code == 200:
                # Проверяем content-type
                content_type = response.headers.get('content-type', '')
                if 'markdown' in content_type or 'text' in content_type or 'md' in content_type:
                    return response.text
                # Если JSON, возможно там есть markdown поле
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        # Ищем markdown в разных полях
                        for key in ['markdown', 'content', 'text', 'md', 'data']:
                            if key in data and isinstance(data[key], str):
                                return data[key]
                        # Если есть summary, пробуем его
                        if 'summary' in data:
                            summary = data['summary']
                            if isinstance(summary, str):
                                return summary
                            elif isinstance(summary, dict) and 'content' in summary:
                                return summary['content']
                except:
                    pass
                # Если не JSON, возвращаем как текст
                return response.text
        except Exception as e:
            continue
    
    # Если не получилось через export, используем /ai/query_source для получения содержимого
    try:
        headers = {"file-id": file_id}
        response = session.get("https://api.plaud.ai/ai/query_source", headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 0 and "data" in data:
                source_data = data["data"]
                # Извлекаем содержимое из source_list
                if "source_list" in source_data and source_data["source_list"]:
                    content_parts = []
                    for source in source_data["source_list"]:
                        if "data_content" in source:
                            content = source["data_content"]
                            # Если это JSON строка, парсим её
                            if isinstance(content, str):
                                try:
                                    import json
                                    content = json.loads(content)
                                    if isinstance(content, list):
                                        for item in content:
                                            if isinstance(item, dict) and "content" in item:
                                                content_parts.append(item["content"])
                                    elif isinstance(content, dict) and "content" in content:
                                        content_parts.append(content["content"])
                                except:
                                    content_parts.append(content)
                            elif isinstance(content, (dict, list)):
                                # Рекурсивно ищем content
                                def extract_content(obj):
                                    if isinstance(obj, str):
                                        return obj
                                    elif isinstance(obj, dict):
                                        if "content" in obj:
                                            return obj["content"]
                                        for v in obj.values():
                                            result = extract_content(v)
                                            if result:
                                                return result
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            result = extract_content(item)
                                            if result:
                                                return result
                                    return None
                                
                                extracted = extract_content(content)
                                if extracted:
                                    content_parts.append(extracted)
                    
                    if content_parts:
                        # Объединяем все части в markdown
                        title = source_data.get("source_group_title", filename)
                        md_content = f"# {title}\n\n"
                        md_content += "\n\n".join(content_parts)
                        return md_content
                else:
                    # Если source_list пустой, создаем базовый markdown с информацией о файле
                    title = source_data.get("source_group_title", filename)
                    md_content = f"# {title}\n\n"
                    if file_info:
                        md_content += f"**Файл:** {file_info.get('filename', file_id)}\n"
                        if file_info.get('duration'):
                            duration_sec = file_info['duration'] / 1000
                            minutes = int(duration_sec // 60)
                            seconds = int(duration_sec % 60)
                            md_content += f"**Длительность:** {minutes}:{seconds:02d}\n"
                        if file_info.get('start_time'):
                            from datetime import datetime
                            start_dt = datetime.fromtimestamp(file_info['start_time'] / 1000)
                            md_content += f"**Дата:** {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    md_content += "\n\n*Транскрипция или summary для этого файла пока недоступны.*"
                    return md_content
    except Exception as e:
        pass
    
    return None


def export_folder(session, folder_name: str, tag_id: str = None, category_id: str = None, export_dir: str = "exports"):
    """Экспортирует все файлы из папки в MD формат."""
    # Получаем список файлов из папки
    print(f"📂 Получение списка файлов из папки '{folder_name}'...")
    
    params = {
        "skip": 0,
        "limit": 99999,
        "is_trash": 0,
        "sort_by": "start_time",
        "is_desc": "true",
    }
    
    if tag_id:
        params["tagId"] = tag_id
    if category_id:
        params["categoryId"] = category_id
    
    response = session.get("https://api.plaud.ai/file/simple/web", params=params, timeout=30)
    
    if response.status_code != 200:
        sys.stderr.write(f"❌ Ошибка получения списка файлов: {response.status_code}\n")
        sys.exit(1)
    
    data = response.json()
    if data.get("status") != 0:
        sys.stderr.write(f"❌ Ошибка API: {data.get('msg', 'Unknown error')}\n")
        sys.exit(1)
    
    all_files = data.get("data_file_list", [])
    
    # Фильтруем файлы: если указан tag_id, проверяем что файл действительно в этой папке
    if tag_id:
        files = []
        for file_info in all_files:
            file_tag_ids = file_info.get("filetag_id_list", [])
            # Файл должен иметь наш tag_id в списке тегов
            if tag_id in file_tag_ids:
                files.append(file_info)
    else:
        files = all_files
    
    total = len(files)
    
    if total == 0:
        print(f"⚠️  В папке '{folder_name}' нет файлов")
        if tag_id and len(all_files) > 0:
            print(f"   (API вернул {len(all_files)} файлов, но ни один не имеет tag_id {tag_id})")
        return
    
    print(f"✅ Найдено файлов в папке '{folder_name}': {total}")
    if tag_id and len(all_files) > total:
        print(f"   (Отфильтровано {len(all_files) - total} файлов, не принадлежащих этой папке)")
    
    # Создаем директорию для экспорта
    export_path = Path(export_dir) / folder_name
    export_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Экспорт в: {export_path.absolute()}")
    
    # Экспортируем каждый файл
    exported = 0
    failed = 0
    
    for i, file_info in enumerate(files, 1):
        file_id = file_info.get("id")
        filename = file_info.get("filename", file_id)
        
        # Очищаем имя файла от недопустимых символов
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        if not safe_filename:
            safe_filename = file_id
        
        file_path = export_path / f"{safe_filename}.md"
        
        print(f"[{i}/{total}] Экспорт: {filename}...", end=" ", flush=True)
        
        md_content = export_file_to_md(session, file_id, filename, file_info)
        
        if md_content:
            try:
                file_path.write_text(md_content, encoding='utf-8')
                print("✅")
                exported += 1
            except Exception as e:
                print(f"❌ Ошибка записи: {e}")
                failed += 1
        else:
            print("❌ Не удалось получить содержимое")
            failed += 1
        
        # Небольшая задержка между запросами
        time.sleep(0.5)
    
    print(f"\n📊 Итого: экспортировано {exported}, ошибок {failed}")


def export_all_folders(session, export_dir: str = "exports"):
    """Экспортирует все папки в MD формат."""
    print("📂 Получение списка всех папок...")
    
    # Получаем список всех папок
    tags_response = session.get("https://api.plaud.ai/filetag/", timeout=30)
    if tags_response.status_code != 200:
        sys.stderr.write(f"❌ Ошибка получения списка папок: {tags_response.status_code}\n")
        sys.exit(1)
    
    tags_data = tags_response.json()
    if tags_data.get("status") != 0:
        sys.stderr.write(f"❌ Ошибка API: {tags_data.get('msg', 'Unknown error')}\n")
        sys.exit(1)
    
    tags = tags_data.get("data_filetag_list", [])
    total = len(tags)
    
    if total == 0:
        print("⚠️  Папок не найдено")
        return
    
    print(f"✅ Найдено папок: {total}\n")
    
    # Экспортируем каждую папку
    exported_folders = 0
    failed_folders = 0
    
    for i, tag in enumerate(tags, 1):
        folder_name = tag.get("name", "")
        tag_id = tag.get("id")
        
        if not folder_name or not tag_id:
            continue
        
        print(f"[{i}/{total}] 📁 Экспорт папки '{folder_name}'...")
        
        try:
            export_folder(session, folder_name, tag_id, folder_name, export_dir)
            exported_folders += 1
            print()  # Пустая строка для разделения
        except Exception as e:
            print(f"❌ Ошибка экспорта папки '{folder_name}': {e}\n")
            failed_folders += 1
    
    print(f"\n📊 Итого: экспортировано папок {exported_folders}, ошибок {failed_folders}")


def main():
    parser = argparse.ArgumentParser(
        description="Клиент для работы с Plaud API. Получение списка директорий и записей."
    )
    parser.add_argument(
        "--list-tags",
        action="store_true",
        help="Получить список всех директорий/тегов (endpoint: /filetag/)",
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="Получить список записей/файлов (endpoint: /file/simple/web)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Количество элементов для запроса (по умолчанию 50)",
    )
    parser.add_argument(
        "--include-trash",
        action="store_true",
        help="Включить записи из корзины (is_trash=2)",
    )
    parser.add_argument(
        "--tag-id",
        help="Фильтр по ID тега/директории (например: 2aa8d467fac50b36b3df523c65a177d5)",
    )
    parser.add_argument(
        "--category-id",
        help="Фильтр по названию категории (например: nubes, 'highload 2026')",
    )
    parser.add_argument(
        "--sort-by",
        default="start_time",
        choices=["start_time", "edit_time"],
        help="Поле сортировки (по умолчанию start_time)",
    )
    parser.add_argument(
        "--sort-asc",
        action="store_true",
        help="Сортировать по возрастанию (по умолчанию по убыванию)",
    )
    parser.add_argument(
        "--endpoint",
        help="Произвольный endpoint для запроса (если не используется --list-tags или --list-files)",
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=["GET", "POST"],
        help="HTTP метод для произвольного запроса (по умолчанию GET)",
    )
    parser.add_argument(
        "--data",
        help="JSON тело для POST запроса",
    )
    parser.add_argument(
        "--export-folder",
        help="Экспортировать все файлы из папки. Укажите название папки (например: nubes) или tag-id",
    )
    parser.add_argument(
        "--export-dir",
        default="exports",
        help="Директория для экспорта (по умолчанию: exports)",
    )
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="Экспортировать все папки в MD формат",
    )

    args = parser.parse_args()

    bearer = load_token()
    session = build_session(bearer)

    # Экспорт всех папок
    if args.export_all:
        export_all_folders(session, args.export_dir)
        return

    # Экспорт папки
    if args.export_folder:
        # Пытаемся найти tag_id по названию папки
        tag_id = None
        category_id = None
        
        # Если передан tag-id, используем его
        if args.tag_id:
            tag_id = args.tag_id
            category_id = args.category_id or args.export_folder
        else:
            # Пытаемся найти папку по названию
            print(f"🔍 Поиск папки '{args.export_folder}'...")
            tags_response = session.get("https://api.plaud.ai/filetag/", timeout=30)
            if tags_response.status_code == 200:
                tags_data = tags_response.json()
                if tags_data.get("status") == 0:
                    tags = tags_data.get("data_filetag_list", [])
                    for tag in tags:
                        if tag.get("name", "").lower() == args.export_folder.lower():
                            tag_id = tag.get("id")
                            category_id = tag.get("name")
                            print(f"✅ Найдена папка: {tag.get('name')} (id: {tag_id})")
                            break
                    
                    if not tag_id:
                        print(f"⚠️  Папка '{args.export_folder}' не найдена. Используем как category_id")
                        category_id = args.export_folder
            else:
                print(f"⚠️  Не удалось получить список папок. Используем '{args.export_folder}' как category_id")
                category_id = args.export_folder
        
        export_folder(session, args.export_folder, tag_id, category_id, args.export_dir)
        return

    # Определяем endpoint и параметры
    if args.list_tags:
        endpoint = "https://api.plaud.ai/filetag/"
        method = "GET"
        data = None
    elif args.list_files:
        trash_flag = 2 if args.include_trash else 0
        is_desc = "false" if args.sort_asc else "true"
        
        params = {
            "skip": 0,
            "limit": args.limit,
            "is_trash": trash_flag,
            "sort_by": args.sort_by,
            "is_desc": is_desc,
        }
        
        if args.tag_id:
            params["tagId"] = args.tag_id
        if args.category_id:
            params["categoryId"] = args.category_id
        
        # Формируем URL с параметрами
        endpoint = "https://api.plaud.ai/file/simple/web"
        method = "GET"
        data = None
        # Используем params для requests
        response = session.get(endpoint, params=params, timeout=30)
        
        print(f"Статус: {response.status_code}")
        print(f"URL: {response.url}")
        print("\nЗаголовки ответа:")
        for k, v in response.headers.items():
            print(f"  {k}: {v}")
        
        try:
            body = response.json()
            body_pretty = json.dumps(body, ensure_ascii=False, indent=2)
        except ValueError:
            body_pretty = response.text
        print("\nТело ответа:")
        print(body_pretty)
        return
    elif args.endpoint:
        endpoint = args.endpoint
        method = args.method.upper()
        data = json.loads(args.data) if args.data else None
    else:
        parser.print_help()
        sys.exit(1)

    # Выполняем запрос
    try:
        response = session.request(method, endpoint, json=data, timeout=30)
    except Exception as exc:
        sys.stderr.write(f"Ошибка при запросе {endpoint}: {exc}\n")
        sys.exit(1)

    print(f"Статус: {response.status_code}")
    print(f"URL: {response.url}")
    print("\nЗаголовки ответа:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")

    try:
        body = response.json()
        body_pretty = json.dumps(body, ensure_ascii=False, indent=2)
    except ValueError:
        body_pretty = response.text
    print("\nТело ответа:")
    print(body_pretty)


if __name__ == "__main__":
    main()

