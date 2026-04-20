# Инструкции по запуску

## ✅ Что уже готово

- ✅ Структура проекта
- ✅ requirements.txt с зависимостями
- ✅ bot.py с основной логикой
- ✅ sheets_manager.py для работы с Google Sheets
- ✅ knowledge_base.py и 5 файлов с книгами
- ✅ .env.example с переменными

## 🚀 Что нужно сделать перед запуском

### Шаг 1. Установи зависимости

```bash
cd /Users/artem/Documents/Agents/finance_agent
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# или для Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Шаг 2. Получи Anthropic API ключ

1. Перейди на https://console.anthropic.com/
2. Создай API ключ
3. Скопируй его (начинается с `sk-ant-`)

### Шаг 3. Создай Telegram бота

1. Напиши @BotFather в Telegram
2. Напиши `/newbot`
3. Выбери имя бота (например, `tea_advisor_bot`)
4. Выбери username (например, `tea_advisor_artem_bot`)
5. Получишь токен (сохрани его)

### Шаг 4. Получи свой Telegram User ID

1. Напиши @userinfobot в Telegram
2. Бот ответит с твоим User ID (число вроде 123456789)

### Шаг 5. Создай Google Sheets таблицу и получи credentials

1. Перейди на https://console.cloud.google.com/
2. Создай новый проект (назови его "Tea Finance")
3. Включи два API:
   - Google Sheets API
   - Google Drive API

4. Создай Service Account:
   - Слева меню → "Service Accounts"
   - Создай новый сервис аккаунт
   - Дай ему имя (например, "tea-finance-bot")
   - Создай JSON ключ

5. Скачай JSON файл и положи его в папку `config/google_credentials.json`

6. Создай таблицу в Google Sheets:
   - Перейди на https://sheets.google.com/
   - Создай новую таблицу "Финансы Чайного Магазина"
   - Скопируй её ID из ссылки (между /d/ и /edit)
   - Пример: https://docs.google.com/spreadsheets/d/**1ABC2DE3FG4H5I6J7K8L9M0N1O2P3Q4R**/edit
   - ID это: `1ABC2DE3FG4H5I6J7K8L9M0N1O2P3Q4R`

7. Поделись таблицей с сервисным аккаунтом:
   - Открой таблицу
   - Кнопка "Share" (Поделиться)
   - Email сервисного аккаунта можно найти в JSON файле (поле "client_email")
   - Дай доступ "Editor"

### Шаг 6. Создай .env файл

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
```

Отредактируй `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...  # Твой ключ от Anthropic
TELEGRAM_BOT_TOKEN=123456789:ABCDefGHIjklMNOpqrSTUvwxyz  # От @BotFather
TELEGRAM_USER_ID=987654321  # От @userinfobot
GOOGLE_SHEET_ID=1ABC2DE3FG4H5I6J7K8L9M0N1O2P3Q4R  # Из ссылки таблицы
GOOGLE_CREDENTIALS_PATH=config/google_credentials.json  # Путь к JSON
```

### Шаг 7. Запусти бота

```bash
python src/bot.py
```

Когда видишь в консоли "Бот запущен...", всё работает!

### Шаг 8. Протестируй в Telegram

1. Найди своего бота в Telegram (по username)
2. Напиши `/start`
3. Бот должен ответить с приветствием

Попробуй команды:
- `/доход 5000 продажа пуэра`
- `/расход 1000 аренда`
- `/итоги`

## 🆘 Если что-то не работает

### "ModuleNotFoundError: No module named 'anthropic'"
Ты не установил зависимости. Запусти:
```bash
pip install -r requirements.txt
```

### "FileNotFoundError: Файл учётных данных Google не найден"
Положи JSON файл от Google в папку `config/google_credentials.json`

### "Telegram bot не отвечает"
Проверь:
- Правильный ли `TELEGRAM_BOT_TOKEN` в `.env`?
- Бот запущен? (видишь "Бот запущен..." в консоли?)

### "Ошибка при подключении к Google Sheets"
Проверь:
- Правильный ли `GOOGLE_SHEET_ID`?
- Поделилась ли ты таблицей с email сервисного аккаунта?
- Включены ли Google Sheets и Drive API в консоли?

## 📝 Следующие улучшения

После запуска можешь просить Claude Code добавить:
- Команду для получения советов по финансовым книгам
- Ежедневные напоминания в определённое время
- Отчёты с графиками расходов
- Распознавание текста от чеков (фото → сумма)

Просто скажи: "Добавь команду /совет" и Claude Code это сделает.
