# 🚀 Быстрый старт (3 минуты)

## Шаг 1️⃣ Скопируй пример окружения
```bash
cd /Users/artem/Documents/Agents/finance_agent
cp .env.example .env
```

## Шаг 2️⃣ Заполни `.env` ключами
Отредактируй файл `.env` и добавь:
```
ANTHROPIC_API_KEY=sk-ant-...           # Получи на https://console.anthropic.com/
TELEGRAM_BOT_TOKEN=123:ABC...          # Получи от @BotFather в Telegram
TELEGRAM_USER_ID=987654321             # Получи от @userinfobot в Telegram
GOOGLE_SHEET_ID=1ABC2DEF...            # Из ссылки таблицы Google Sheets
GOOGLE_CREDENTIALS_PATH=config/google_credentials.json
```

**Где получить ключи:**
- 🔑 Anthropic: https://console.anthropic.com/ → API Keys
- 🤖 Telegram Bot: напиши @BotFather → /newbot
- 👤 Telegram User ID: напиши @userinfobot
- 📊 Google: https://console.cloud.google.com/ → Service Account (скачай JSON в `config/`)

## Шаг 3️⃣ Установи зависимости
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Шаг 4️⃣ Запусти бота
```bash
python src/bot.py
```

Когда видишь в консоли **"Бот запущен..."** — всё работает! ✅

## Шаг 5️⃣ Протестируй в Telegram
Напиши боту (найди по username):
- `/start` — приветствие
- `/доход 5000 продажа` — добавить доход
- `/расход 1000 аренда` — добавить расход
- `/итоги` — отчёт за день

## 📚 Полная инструкция
Если что-то не работает, читай `SETUP.md`

## 🎯 Следующие команды для Claude Code
После запуска можешь просить улучшения:
- "Добавь команду /совет для получения советов"
- "Добавь ежедневные напоминания в 8:00, 14:00, 21:00"
- "Добавь отчёты с графиками расходов"
