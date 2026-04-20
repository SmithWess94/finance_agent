import os
import logging
import base64
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic
from src.sheets_manager import SheetsManager
from src.knowledge_base import load_knowledge_base
from src.cache_manager import CacheManager

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создать файл credentials из переменной окружения (base64 encoded)
google_creds_b64 = os.getenv('GOOGLE_CREDENTIALS_B64')
if google_creds_b64:
    os.makedirs('config', exist_ok=True)
    try:
        creds_json = base64.b64decode(google_creds_b64).decode()
        with open('config/google_credentials.json', 'w') as f:
            f.write(creds_json)
        logger.info("Google credentials loaded from environment variable")
    except Exception as e:
        logger.error(f"Failed to decode credentials: {e}")

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = int(os.getenv('TELEGRAM_USER_ID', 0))

client = Anthropic(api_key=ANTHROPIC_API_KEY)
sheets_manager = SheetsManager()
knowledge_base = load_knowledge_base()
cache_manager = CacheManager()

class TeaAdvisor:
    def __init__(self):
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self):
        return """Ты финансовый наставник для владельца чайного магазина.

Задачи:
1. Погасить долги перед поставщиками
2. Накопить подушку безопасности (3-6 месяцев расходов)
3. Выстроить дисциплину в учёте доходов/расходов
4. Изменить финансовое мышление

Базовые принципы:
- Доход = сумма денег, которую ты заработал
- Расход = потраченные деньги на ведение бизнеса
- Долг = обязательство перед поставщиками
- Подушка = резерв на 3-6 месяцев без доходов

Стиль: прямо, без лишнего. Честный и мотивирующий. Показывай связь между сегодняшними действиями и завтрашним результатом.

Когда пользователь просит совет, базируйся на концепциях классических финансовых книг: важность расчётов, изменение мышления, долгосрочное планирование.
"""
    
    def get_advice(self, user_message):
        cached_answer = cache_manager.get(user_message)
        if cached_answer:
            return cached_answer

        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=self.system_prompt,
            messages=self.conversation_history
        )

        assistant_message = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        cache_manager.set(user_message, assistant_message)
        return assistant_message

advisor = TeaAdvisor()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и начало работы."""
    user = update.effective_user
    message = f"""Привет, {user.first_name}! 🍵

Я твой финансовый наставник. Помогу тебе:
✓ Погасить долги перед поставщиками чая
✓ Накопить финансовую подушку
✓ Выстроить дисциплину в учёте доходов и расходов
✓ Изменить твоё финансовое мышление

Команды:
/income <сумма> <описание> - добавить доход
/expense <сумма> <категория> - добавить расход
/debt <поставщик> <сумма> - добавить долг
/summary - отчёт за день/неделю/месяц
/advice - получить совет

Или просто напиши мне в естественном языке!"""
    
    await update.message.reply_text(message)

async def handle_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /доход."""
    try:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Использование: /доход <сумма> <описание>")
            return
        
        amount = float(context.args[0])
        description = ' '.join(context.args[1:])
        
        sheets_manager.add_income(amount, description)
        
        response = advisor.get_advice(f"Я только что заработал {amount} рублей на {description}. Как дела?")
        await update.message.reply_text(f"✅ Доход {amount}₽ записан!\n\n{response}")
    except ValueError:
        await update.message.reply_text("Ошибка: первый аргумент должен быть числом")
    except Exception as e:
        logger.error(f"Error in handle_income: {e}")
        await update.message.reply_text("Ошибка при записи дохода")

async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /расход."""
    try:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Использование: /расход <сумма> <категория>")
            return
        
        amount = float(context.args[0])
        category = ' '.join(context.args[1:])
        
        sheets_manager.add_expense(amount, category)
        
        response = advisor.get_advice(f"Я потратил {amount} рублей на {category}. Это нормально?")
        await update.message.reply_text(f"✅ Расход {amount}₽ записан!\n\n{response}")
    except ValueError:
        await update.message.reply_text("Ошибка: первый аргумент должен быть числом")
    except Exception as e:
        logger.error(f"Error in handle_expense: {e}")
        await update.message.reply_text("Ошибка при записи расхода")

async def handle_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /долг."""
    try:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Использование: /долг <поставщик> <сумма>")
            return
        
        supplier = context.args[0]
        amount = float(context.args[1])
        
        sheets_manager.add_debt(supplier, amount)
        
        response = advisor.get_advice(f"У меня есть долг {amount} рублей перед {supplier}")
        await update.message.reply_text(f"✅ Долг {amount}₽ перед {supplier} записан!\n\n{response}")
    except ValueError:
        await update.message.reply_text("Ошибка: сумма должна быть числом")
    except Exception as e:
        logger.error(f"Error in handle_debt: {e}")
        await update.message.reply_text("Ошибка при записи долга")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка естественного языка."""
    try:
        user_message = update.message.text
        response = advisor.get_advice(user_message)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке сообщения")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отчёт за день."""
    try:
        stats = sheets_manager.get_daily_summary()
        response = advisor.get_advice(f"Вот мой отчёт за день: {stats}")
        await update.message.reply_text(f"📊 Итоги дня:\n{stats}\n\n{response}")
    except Exception as e:
        logger.error(f"Error in summary: {e}")
        await update.message.reply_text("Ошибка при получении отчёта")

def main():
    """Запуск бота."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("income", handle_income))
    app.add_handler(CommandHandler("expense", handle_expense))
    app.add_handler(CommandHandler("debt", handle_debt))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    webhook_url = os.getenv('WEBHOOK_URL')
    port = int(os.getenv('PORT', 8080))

    if webhook_url:
        logger.info(f"Бот запущен в режиме webhook на порту {port}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"{webhook_url}/webhook",
        )
    else:
        logger.info("Бот запущен в режиме polling...")
        app.run_polling()

if __name__ == '__main__':
    main()
