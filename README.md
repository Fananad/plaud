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

Экспорт всех директорий в папку `exports/`:

```bash
python client.py
```

Указать другую папку для экспорта:

```bash
python client.py --export-dir my_exports
```

Файлы сохраняются в `exports/<название_папки>/` в формате Markdown (транскрипция, заметки, summary).
