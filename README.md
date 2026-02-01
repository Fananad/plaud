# Plaud → Markdown

Экспорт всех папок Plaud в Markdown.

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Создайте файл `.token` в корне репозитория с bearer-токеном Plaud (можно подсмотреть из status):

```bash
echo "your_token_here" > .token
```

## Запуск

**Все папки** — экспорт в `obsi/`:

```bash
python client.py
```

**Одна папка** — по имени (например `daily`, `nubes`):

```bash
python client.py --folder daily
python client.py --folder nubes
```

Другая папка для экспорта:

```bash
python client.py --export-dir my_exports
python client.py --folder daily --export-dir my_exports
```

**После экспорта переносить записи в корзину** в Plaud (по одной после записи на диск):

```bash
python client.py --delete
python client.py --folder daily --delete
```

Файлы сохраняются в `obsi/<название_папки>/` в формате Markdown (транскрипция, заметки, summary).
