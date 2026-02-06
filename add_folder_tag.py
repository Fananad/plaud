#!/usr/bin/env python3
"""
Добавляет первым тегом в каждом .md имя корневой папки (первая папка под obsi).
Запуск из каталога plaud: python3 add_folder_tag.py
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
OBSI = REPO / "obsi"
TAG_LINE = re.compile(r"^tag\s+(.+)$", re.MULTILINE)


def get_root_folder(rel_path: str) -> str:
    parts = Path(rel_path).parts
    return parts[0] if parts else ""


def ensure_first_tag(content: str, root_tag: str) -> str:
    """Делает root_tag первым в строке tag. Возвращает новое содержимое."""
    tag_hash = f"#{root_tag}"
    match = TAG_LINE.search(content)
    if not match:
        # Нет строки tag — добавить в начало файла
        insert = f"tag {tag_hash}\n\n"
        return insert + content

    existing = match.group(1).strip()
    tags = re.findall(r"#\S+", existing)
    if not tags:
        new_line = f"tag {tag_hash}"
    elif tags[0].lower() == tag_hash.lower():
        return content  # уже первый
    else:
        rest = [t for t in tags if t.lower() != tag_hash.lower()]
        new_line = f"tag {tag_hash} " + " ".join(rest)
    return TAG_LINE.sub(new_line, content, count=1)


def main():
    if not OBSI.exists():
        print(f"Папка не найдена: {OBSI}")
        return
    updated = 0
    for path in sorted(OBSI.rglob("*.md")):
        try:
            rel = path.relative_to(OBSI)
            root = get_root_folder(str(rel))
            if not root:
                continue
            text = path.read_text(encoding="utf-8")
            new_text = ensure_first_tag(text, root)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                updated += 1
                print(rel)
        except Exception as e:
            print(f"  ❌ {rel}: {e}")
    print(f"\nОбновлено: {updated} файлов")


if __name__ == "__main__":
    main()
