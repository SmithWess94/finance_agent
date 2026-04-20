# Финансовый агент-наставник

Персональный ИИ-финансист в Telegram. Ведёт учёт в Google Sheets, даёт советы на основе 5 классических книг о деньгах, напоминает о записях трижды в день.

---

## Что умеет

**Учёт финансов** — просто пишешь боту как обычно:
- «Заработал 3000 на церемонии» → записывает в Google Sheets
- «Потратил 800 на продукты» → записывает расход по категории
- «Должен поставщику 5000» → фиксирует долг

**Команды:**
| Команда | Действие |
|---|---|
| `/start` | Приветствие |
| `/совет` | Контекстный совет из базы знаний по текущей ситуации |
| `/итоги` | Отчёт за день с комментарием |

**Ежедневные напоминания** (по Киеву):
| Время | Что происходит |
|---|---|
| 08:00 | Мудрость из книг + намерение на день |
| 14:00 | Проверка записей, мягкий толчок если пусто |
| 21:00 | Вечерние итоги + вопрос для рефлексии |
| 21:30 | Если таблица за день пуста — последнее напоминание |

**Telegram Mini App** — веб-дашборд прямо в Telegram (кнопка в `/start`):
- Снапшот дня: доходы / расходы / баланс
- Список долгов с прогрессом погашения
- Быстрый ввод операций
- Чат с наставником

---

## Архитектура

```
Telegram ──→ Webhook ──→ FastAPI (src/api.py)
                              │
                    ┌─────────┴─────────┐
                    │                   │
              Telegram Bot         REST API
              (handlers +          (/api/snapshot,
               job_queue)           /api/income, ...)
                    │                   │
              Claude API          Google Sheets
              + Knowledge Base
```

**Стек:** Python · FastAPI · python-telegram-bot · Anthropic Claude · gspread · APScheduler

---

## База знаний

5 книг в `knowledge_base/`, загружаются в системный промт Claude:

1. `kiyosaki.md` — Богатый папа, бедный папа
2. `babylon.md` — Самый богатый человек в Вавилоне
3. `housel.md` — Психология денег
4. `hill.md` — Думай и богатей
5. `schaefer.md` — Путь к финансовой свободе

---

## Запуск локально

```bash
cp .env.example .env
# заполни .env ключами

pip install -r requirements.txt
uvicorn src.api:app --reload
```

Переменные окружения:
```
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_JSON=   # base64-encoded JSON от Google Service Account
WEBHOOK_URL=               # публичный URL сервера (для webhook)
```

---

## Деплой

Проект развёрнут на Render. Procfile:
```
web: uvicorn src.api:app --host 0.0.0.0 --port $PORT
```
