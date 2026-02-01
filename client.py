#!/usr/bin/env python3
"""
Экспорт всех папок Plaud в Markdown.
"""
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.stderr.write(
        "Не найден модуль requests. Установите: pip install -r requirements.txt\n"
    )
    raise

import gzip

REPO_ROOT = Path(__file__).resolve().parent
TOKEN_FILE = REPO_ROOT / ".token"


def fix_double_encoding(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        fixed = text.encode("latin-1").decode("utf-8")
        if "\x00" not in fixed and not any(ord(c) > 0x10FFFF for c in fixed):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def load_token() -> str:
    if not TOKEN_FILE.exists():
        sys.stderr.write(f"Файл с токеном не найден: {TOKEN_FILE}\n")
        sys.stderr.write("Создайте .token в корне репозитория с bearer токеном.\n")
        sys.exit(1)
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        sys.stderr.write("Файл .token пуст.\n")
        sys.exit(1)
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def build_session(bearer: str):
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


def get_all_transcripts_from_detail(session, file_id: str):
    try:
        response = session.get(
            f"https://api.plaud.ai/file/detail/{file_id}", timeout=30
        )
        if response.status_code != 200:
            return []
        data = response.json()
        if data.get("status") != 0:
            return []
        content_list = data.get("data", {}).get("content_list", [])
        transcripts = []
        for content in content_list:
            data_link = content.get("data_link")
            if not data_link:
                continue
            try:
                resp = requests.get(data_link, timeout=30)
                if resp.status_code != 200:
                    continue
                if data_link.endswith(".gz"):
                    content_data = gzip.decompress(resp.content).decode("utf-8")
                else:
                    try:
                        content_data = resp.content.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            content_data = (
                                resp.content.decode("latin-1")
                                .encode("latin-1")
                                .decode("utf-8")
                            )
                        except Exception:
                            content_data = resp.text
                try:
                    parsed = json.loads(content_data)
                except json.JSONDecodeError:
                    parsed = content_data if content_data.strip() else None
                if parsed is not None:
                    transcripts.append(
                        {
                            "type": content.get("data_type", ""),
                            "data_tab_name": content.get("data_tab_name", ""),
                            "data_title": content.get("data_title", ""),
                            "content": parsed,
                        }
                    )
            except Exception:
                continue
        return transcripts
    except Exception:
        return []


def export_file_to_md(session, file_id: str, filename: str, file_info: dict = None):
    transcripts = get_all_transcripts_from_detail(session, file_id)
    if not transcripts:
        try:
            response = session.get(
                "https://api.plaud.ai/ai/query_source",
                headers={"file-id": file_id},
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 0 and "data" in data:
                    source_data = data["data"]
                    title = source_data.get("source_group_title", filename)
                    md = f"# {title}\n\n"
                    if file_info:
                        md += f"**Файл:** {file_info.get('filename', file_id)}\n"
                        if file_info.get("duration"):
                            s = file_info["duration"] / 1000
                            md += f"**Длительность:** {int(s // 60)}:{int(s % 60):02d}\n"
                        if file_info.get("start_time"):
                            from datetime import datetime
                            md += f"**Дата:** {datetime.fromtimestamp(file_info['start_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    md += "\n*Транскрипция недоступна.*"
                    return md
        except Exception:
            pass
        return None

    type_order = {
        "transaction": 1,
        "outline": 2,
        "auto_sum_note": 3,
        "sum_multi_note": 4,
        "consumer_note": 5,
    }
    sorted_transcripts = sorted(
        transcripts, key=lambda x: type_order.get(x.get("type", ""), 99)
    )
    md_parts = []
    title = filename

    for t in sorted_transcripts:
        data_type = t.get("type", "")
        content = t.get("content", "")
        data_tab_name = t.get("data_tab_name", "")
        data_title = t.get("data_title", "")

        if data_type == "transaction" and isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "content" in item:
                    md_parts.append(item["content"])
        elif data_type == "outline" and isinstance(content, list):
            parts = [
                f"- {item['topic']}"
                for item in content
                if isinstance(item, dict) and "topic" in item
            ]
            if parts:
                md_parts.append("## План\n\n" + "\n".join(parts))
        elif data_type == "auto_sum_note":
            sect = data_tab_name or "Summary"
            text = (
                content.get("ai_content") or content.get("content")
                or content.get("text") or content.get("summary")
                if isinstance(content, dict) else content
            )
            if isinstance(text, str) and text.strip():
                md_parts.append(f"## {sect}\n\n{text}")
        elif data_type == "sum_multi_note":
            sect = data_tab_name or data_title or "Summary"
            if isinstance(content, dict):
                text = content.get("ai_content") or content.get("content") or content.get("text") or content.get("summary")
                if text and str(text).strip():
                    md_parts.append(f"## {sect}\n\n{text}")
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        t = item.get("ai_content") or item.get("content") or item.get("text") or item.get("summary")
                        if t:
                            text_parts.append(str(t))
                    elif isinstance(item, str):
                        text_parts.append(item)
                if text_parts:
                    md_parts.append(f"## {sect}\n\n" + "\n\n".join(text_parts))
        elif data_type == "consumer_note" and isinstance(content, str) and content.strip():
            md_parts.append("## Заметки\n\n" + fix_double_encoding(content))
        elif isinstance(content, str) and content.strip():
            md_parts.append(content)

    if not md_parts:
        return None
    return f"# {title}\n\n" + "\n\n".join(md_parts)


def export_folder(session, folder_name: str, tag_id: str, export_base: Path):
    params = {
        "skip": 0,
        "limit": 99999,
        "is_trash": 0,
        "sort_by": "start_time",
        "is_desc": "true",
        "tagId": tag_id,
        "categoryId": folder_name,
    }
    response = session.get(
        "https://api.plaud.ai/file/simple/web", params=params, timeout=30
    )
    if response.status_code != 200:
        raise RuntimeError(f"Ошибка API: {response.status_code}")
    data = response.json()
    if data.get("status") != 0:
        raise RuntimeError(data.get("msg", "Unknown error"))
    all_files = data.get("data_file_list", [])
    files = [
        f for f in all_files
        if tag_id in f.get("filetag_id_list", [])
    ]
    if not files:
        print(f"  ⚠️ Нет файлов")
        return
    export_path = export_base / folder_name
    export_path.mkdir(parents=True, exist_ok=True)
    print(f"  📁 {export_path.absolute()} ({len(files)} файлов)")
    exported = failed = 0
    for i, file_info in enumerate(files, 1):
        file_id = file_info.get("id")
        filename = file_info.get("filename", file_id)
        safe_name = "".join(
            c for c in filename if c.isalnum() or c in (" ", "-", "_", ".")
        ).strip() or file_id
        md_content = export_file_to_md(session, file_id, filename, file_info)
        if md_content:
            try:
                (export_path / f"{safe_name}.md").write_text(md_content, encoding="utf-8")
                exported += 1
            except Exception as e:
                print(f"  ❌ {filename}: {e}")
                failed += 1
        else:
            failed += 1
        time.sleep(0.5)
    print(f"  ✅ {exported}, ошибок {failed}")


def export_all_folders(session, export_dir: str = "exports"):
    export_base = (
        REPO_ROOT / export_dir
        if not Path(export_dir).is_absolute()
        else Path(export_dir)
    )
    print("📂 Список папок...")
    response = session.get("https://api.plaud.ai/filetag/", timeout=30)
    if response.status_code != 200:
        sys.stderr.write(f"Ошибка: {response.status_code}\n")
        sys.exit(1)
    data = response.json()
    if data.get("status") != 0:
        sys.stderr.write(f"Ошибка API: {data.get('msg', 'Unknown')}\n")
        sys.exit(1)
    tags = data.get("data_filetag_list", [])
    if not tags:
        print("Папок не найдено.")
        return
    print(f"✅ Папок: {len(tags)}\n")
    for i, tag in enumerate(tags, 1):
        name = tag.get("name", "")
        tag_id = tag.get("id")
        if not name or not tag_id:
            continue
        print(f"[{i}/{len(tags)}] 📁 {name}")
        try:
            export_folder(session, name, tag_id, export_base)
        except Exception as e:
            print(f"  ❌ {e}")
        print()
    print("Готово.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Экспорт всех папок Plaud в Markdown.")
    parser.add_argument(
        "--export-dir",
        default="exports",
        help="Папка для экспорта (по умолчанию: exports)",
    )
    args = parser.parse_args()
    session = build_session(load_token())
    export_all_folders(session, args.export_dir)


if __name__ == "__main__":
    main()
