import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic
from src.sheets_manager import SheetsManager
from src.knowledge_base import load_knowledge_base

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = int(os.getenv('TELEGRAM_USER_ID', 0))

client = Anthropic(api_key=ANTHROPIC_API_KEY)
sheets_manager = SheetsManager()
knowledge_base = load_knowledge_base()

TOOLS = [
    {
        "name": "record_income",
        "description": "Записать доход в Google Таблицу. Используй когда пользователь упоминает заработок, выручку, продажу, поступление денег.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Сумма дохода в рублях"},
                "description": {"type": "string", "description": "Откуда пришли деньги (например: продажа чая, опт, розница)"}
            },
            "required": ["amount", "description"]
        }
    },
    {
        "name": "record_expense",
        "description": "Записать расход в Google Таблицу. Используй когда пользователь упоминает трату, расход, покупку, оплату.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Сумма расхода в рублях"},
                "category": {"type": "string", "description": "На что потрачено (например: аренда, закупка, реклама)"}
            },
            "required": ["amount", "category"]
        }
    },
    {
        "name": "record_debt",
        "description": "Записать долг перед поставщиком в Google Таблицу. Используй когда пользователь упоминает долг или обязательство перед поставщиком.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string", "description": "Название поставщика"},
                "amount": {"type": "number", "description": "Сумма долга в рублях"}
            },
            "required": ["supplier", "amount"]
        }
    },
    {
        "name": "get_summary",
        "description": "Получить итоговый отчёт за сегодня: доходы, расходы, баланс. Используй когда пользователь спрашивает про итоги дня или сводку.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]


class TeaAdvisor:
    def __init__(self):
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        return """Ты финансовый наставник для владельца чайного магазина.

У тебя есть инструменты для записи в Google Таблицу:
- record_income — записать доход
- record_expense — записать расход
- record_debt — записать долг перед поставщиком
- get_summary — показать итоги дня

Когда пользователь говорит о деньгах (заработал, потратил, должен) — ВСЕГДА используй нужный инструмент для записи, не спрашивай подтверждения.

Если сумма или описание не указаны — уточни и запиши.

Задачи пользователя:
1. Погасить долги перед поставщиками
2. Накопить подушку безопасности (3-6 месяцев расходов)
3. Выстроить дисциплину в учёте
4. Изменить финансовое мышление

Стиль: прямо, коротко, мотивирующе. Показывай связь между сегодняшними действиями и завтрашним результатом.
"""

    def _execute_tool(self, tool_name, tool_input):
        try:
            if tool_name == "record_income":
                sheets_manager.add_income(tool_input["amount"], tool_input["description"])
                return f"Доход {tool_input['amount']}₽ ({tool_input['description']}) записан в таблицу."
            elif tool_name == "record_expense":
                sheets_manager.add_expense(tool_input["amount"], tool_input["category"])
                return f"Расход {tool_input['amount']}₽ ({tool_input['category']}) записан в таблицу."
            elif tool_name == "record_debt":
                sheets_manager.add_debt(tool_input["supplier"], tool_input["amount"])
                return f"Долг {tool_input['amount']}₽ перед {tool_input['supplier']} записан в таблицу."
            elif tool_name == "get_summary":
                return sheets_manager.get_daily_summary()
            else:
                return "Неизвестный инструмент."
        except Exception as e:
            logger.error(f"Tool error {tool_name}: {e}")
            return f"Ошибка при записи: {e}"

    def chat(self, user_message):
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=self.system_prompt,
            messages=self.conversation_history,
            tools=TOOLS
        )

        if response.stop_reason == "tool_use":
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            final = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=self.system_prompt,
                messages=self.conversation_history,
                tools=TOOLS
            )
            assistant_message = final.content[0].text
        else:
            assistant_message = response.content[0].text

        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        return assistant_message


advisor = TeaAdvisor()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = f"""Привет, {user.first_name}! 🍵

Я твой финансовый наставник. Просто пиши мне как обычно:

"Заработал сегодня 5000 рублей на продаже чая"
"Потратил 1500 на аренду"
"Должен поставщику Иван Иваныч 8000"
"Покажи итоги дня"

Всё запишу в таблицу и дам совет."""

    await update.message.reply_text(message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_message = update.message.text
        response = advisor.chat(user_message)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке сообщения")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats = sheets_manager.get_daily_summary()
        response = advisor.chat(f"Вот мой отчёт за день: {stats}")
        await update.message.reply_text(f"📊 Итоги дня:\n{stats}\n\n{response}")
    except Exception as e:
        logger.error(f"Error in summary: {e}")
        await update.message.reply_text("Ошибка при получении отчёта")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    webhook_url = os.getenv('WEBHOOK_URL')
    port = int(os.getenv('PORT', 8080))

    if webhook_url:
        logger.info(f"Бот запущен в режиме webhook на порту {port}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/webhook",
            webhook_url=f"{webhook_url}/webhook",
        )
    else:
        logger.info("Бот запущен в режиме polling...")
        app.run_polling()


if __name__ == '__main__':
    main()
