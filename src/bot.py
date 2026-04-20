import os
import logging
from datetime import time
from zoneinfo import ZoneInfo
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
KYIV_TZ = ZoneInfo('Europe/Kyiv')

client = Anthropic(api_key=ANTHROPIC_API_KEY)
sheets_manager = SheetsManager()
knowledge_base = load_knowledge_base()

TOOLS = [
    {
        "name": "record_income",
        "description": "Записать доход в Google Таблицу. Используй когда пользователь упоминает заработок, зарплату, выручку, поступление денег.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Сумма дохода в гривнах"},
                "description": {"type": "string", "description": "Источник дохода. Например: Зарплата, Фриланс, Продажи, Аренда, Подработка, Прочее."}
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
                "amount": {"type": "number", "description": "Сумма расхода в гривнах"},
                "category": {
                    "type": "string",
                    "description": "Категория расхода. Выбери подходящую: Еда и продукты, Рестораны и кафе, Транспорт, Жильё, Коммунальные услуги, Здоровье, Одежда, Развлечения, Учёба, Бизнес, Кредит, Прочее."
                }
            },
            "required": ["amount", "category"]
        }
    },
    {
        "name": "record_debt",
        "description": "Записать долг в Google Таблицу. Используй когда пользователь упоминает что кому-то должен денег.",
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string", "description": "Кому должен (имя человека, банк, организация)"},
                "amount": {"type": "number", "description": "Сумма долга в гривнах"}
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

SYSTEM_PROMPT = f"""Ты персональный финансовый наставник. Твоя миссия — провести пользователя от хаоса в финансах к полной ясности и финансовой независимости.

Валюта: гривны (₴). Всегда используй знак ₴.

У тебя есть инструменты для записи в Google Таблицу:
- record_income — записать доход
- record_expense — записать расход
- record_debt — записать долг
- get_summary — показать итоги дня

Когда пользователь говорит о деньгах (заработал, потратил, должен) — СРАЗУ используй нужный инструмент, не спрашивай подтверждения. Если сумма не указана — уточни.

Стиль: конкретно, тепло, без воды. Ты наставник, а не робот. Когда уместно — подкрепляй советы мудростью из книг ниже. Максимум 1-2 emoji.

=== БАЗА ЗНАНИЙ (5 книг о деньгах) ===
{knowledge_base}
"""


class FinanceAdvisor:
    def __init__(self):
        self.conversation_history = []

    def _execute_tool(self, tool_name, tool_input):
        try:
            if tool_name == "record_income":
                sheets_manager.add_income(tool_input["amount"], tool_input["description"])
                return f"Доход {tool_input['amount']}₴ ({tool_input['description']}) записан в таблицу."
            elif tool_name == "record_expense":
                sheets_manager.add_expense(tool_input["amount"], tool_input["category"])
                return f"Расход {tool_input['amount']}₴ ({tool_input['category']}) записан в таблицу."
            elif tool_name == "record_debt":
                sheets_manager.add_debt(tool_input["supplier"], tool_input["amount"])
                return f"Долг {tool_input['amount']}₴ перед {tool_input['supplier']} записан в таблицу."
            elif tool_name == "get_summary":
                return sheets_manager.get_daily_summary()
            else:
                return "Неизвестный инструмент."
        except Exception as e:
            logger.error(f"Tool error {tool_name}: {e}")
            return f"Ошибка при записи: {e}"

    def chat(self, user_message):
        self.conversation_history.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=self.conversation_history,
            tools=TOOLS
        )

        if response.stop_reason == "tool_use":
            self.conversation_history.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            self.conversation_history.append({"role": "user", "content": tool_results})

            final = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=self.conversation_history,
                tools=TOOLS
            )
            assistant_message = final.content[0].text
        else:
            assistant_message = response.content[0].text

        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        return assistant_message


def _one_shot(prompt: str, max_tokens: int = 350) -> str:
    """Одиночный вызов Claude без сохранения истории — для напоминаний и советов."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


advisor = FinanceAdvisor()


# ── Команды ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я твой финансовый наставник. Пиши мне как обычно:\n\n"
        "«Заработал сегодня 3000 на церемонии»\n"
        "«Потратил 800 на продукты»\n"
        "«Покажи итоги дня»\n\n"
        "Команды:\n"
        "/совет — мудрость из книг по твоей ситуации\n"
        "/итоги — отчёт за день\n\n"
        "Всё запишу в таблицу."
    )


def _load_user_profile() -> str:
    profile_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'user_profile.md')
    try:
        with open(profile_path, encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


async def advice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Контекстный совет из базы знаний на основе реального финансового состояния."""
    await update.message.reply_text("Смотрю твою ситуацию...")
    try:
        ctx = sheets_manager.get_rich_context()
        debts = sheets_manager.get_debts()
        profile = _load_user_profile()

        debts_text = "\n".join(
            f"- {d['supplier']}: осталось {d['remaining']}₴ из {d['original']}₴"
            for d in debts if d['remaining'] > 0
        ) or "долгов нет"

        categories_text = "\n".join(
            f"- {cat}: {amt:.0f}₴" for cat, amt in ctx['top_categories']
        ) or "данных пока нет"

        silence_note = (
            f"⚠️ За последние 7 дней было {ctx['days_silent']} дней без единой записи."
            if ctx['days_silent'] > 0 else
            "Молодец — записи есть каждый день на этой неделе."
        )

        prompt = f"""Вот реальная финансовая картина пользователя прямо сейчас.

=== ПРОФИЛЬ ===
{profile}

=== ФИНАНСЫ ===
Сегодня: доход {ctx['today_income']}₴ / расход {ctx['today_expense']}₴ / баланс {ctx['today_balance']}₴
Эта неделя: доход {ctx['week_income']}₴ / расход {ctx['week_expense']}₴ / баланс {ctx['week_balance']}₴
Этот месяц: доход {ctx['month_income']}₴ / расход {ctx['month_expense']}₴ / баланс {ctx['month_balance']}₴
Общий долг: {ctx['total_debt']}₴

Долги:
{debts_text}

Топ категорий расходов за месяц:
{categories_text}

Дисциплина учёта: {silence_note}

=== ЗАДАЧА ===
Дай один конкретный совет — именно для этой ситуации, именно сейчас.
Опирайся на мудрость из книг базы знаний, но переведи её в конкретное действие.
Укажи из какой книги. Максимум 6 предложений. Никакой воды."""

        message = _one_shot(prompt, max_tokens=450)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Advice error: {e}")
        await update.message.reply_text("Не смог получить данные из таблицы. Попробуй ещё раз.")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats = sheets_manager.get_daily_summary()
        response = advisor.chat(f"Вот мой отчёт за сегодня: {stats}. Прокомментируй коротко.")
        await update.message.reply_text(f"📊 {stats}\n\n{response}")
    except Exception as e:
        logger.error(f"Summary error: {e}")
        await update.message.reply_text("Ошибка при получении отчёта.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = advisor.chat(update.message.text)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Message error: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз.")


# ── Напоминания ───────────────────────────────────────────────────────────────

async def reminder_morning(context: ContextTypes.DEFAULT_TYPE):
    """08:00 — утренний заряд и намерение на день."""
    try:
        ctx = sheets_manager.get_rich_context()
        profile = _load_user_profile()
        silence_note = f"Последние {ctx['days_silent']} дней без записей." if ctx['days_silent'] > 1 else ""

        prompt = f"""Сейчас 8 утра. Пользователь начинает день.

Профиль: {profile}

Финансы за неделю: доход {ctx['week_income']}₴, расход {ctx['week_expense']}₴, долг {ctx['total_debt']}₴.
{silence_note}

Напиши утреннее сообщение (3-4 предложения):
- одна мудрость из книг, применимая к его конкретной ситуации прямо сейчас
- один простой вопрос-намерение на сегодня
Тон: живой, тёплый, как от друга-наставника. Без пафоса."""

        message = _one_shot(prompt)
        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=f"☀️ Доброе утро!\n\n{message}")
    except Exception as e:
        logger.error(f"Morning reminder error: {e}")


async def reminder_afternoon(context: ContextTypes.DEFAULT_TYPE):
    """14:00 — дневная проверка."""
    try:
        snapshot = sheets_manager.get_snapshot()
        has_records = snapshot['today_income'] > 0 or snapshot['today_expense'] > 0

        if has_records:
            prompt = (
                f"Сейчас 14:00. У пользователя уже записано за сегодня: "
                f"доход {snapshot['today_income']}₴, расход {snapshot['today_expense']}₴. "
                f"Напиши короткое одобрительное сообщение (2-3 предложения) — "
                f"молодец что записывает, и напомни проверить ещё раз вечером."
            )
        else:
            prompt = (
                f"Сейчас 14:00. Пользователь ещё ничего не записал за сегодня. "
                f"Напиши короткое мягкое напоминание (2-3 предложения) — "
                f"зафиксировать любые движения денег за утро. "
                f"Можно сослаться на принцип из книг базы знаний."
            )

        message = _one_shot(prompt, max_tokens=200)
        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=f"💡 {message}")
    except Exception as e:
        logger.error(f"Afternoon reminder error: {e}")


async def reminder_evening(context: ContextTypes.DEFAULT_TYPE):
    """21:00 — вечерние итоги и рефлексия."""
    try:
        ctx = sheets_manager.get_rich_context()

        prompt = f"""Сейчас вечер, 21:00. Время подводить итоги дня.

Сегодня: доход {ctx['today_income']}₴, расход {ctx['today_expense']}₴, баланс {ctx['today_balance']}₴.
За неделю: доход {ctx['week_income']}₴, расход {ctx['week_expense']}₴.
Общий долг: {ctx['total_debt']}₴.
Дней без записей на этой неделе: {ctx['days_silent']}.

Напиши вечернее сообщение (4-5 предложений):
- честная оценка дня по цифрам
- один вопрос для рефлексии — конкретный, не банальный
- напомни записать всё что не записано
Тон: поддерживающий, прямой."""

        message = _one_shot(prompt)
        await context.bot.send_message(chat_id=TELEGRAM_USER_ID, text=f"🌙 Вечерний итог\n\n{message}")
    except Exception as e:
        logger.error(f"Evening reminder error: {e}")


async def reminder_check(context: ContextTypes.DEFAULT_TYPE):
    """21:30 — если за день ничего не записано, отправить последний толчок."""
    try:
        snapshot = sheets_manager.get_snapshot()
        if snapshot['today_income'] == 0 and snapshot['today_expense'] == 0:
            await context.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=(
                    "Эй, сегодня в таблице пусто 👀\n\n"
                    "Даже если день был тихий — запиши хоть что-то. "
                    "Привычка важнее суммы. Бавилонский купец записывал каждую монету — "
                    "это и был его секрет богатства.\n\n"
                    "Что было сегодня? Напиши мне."
                )
            )
    except Exception as e:
        logger.error(f"Check reminder error: {e}")


# ── Запуск ────────────────────────────────────────────────────────────────────

async def post_init(application: Application):
    """Регистрируем ежедневные задачи после инициализации приложения."""
    jq = application.job_queue
    jq.run_daily(reminder_morning,   time=time(8,  0,  tzinfo=KYIV_TZ), name="morning")
    jq.run_daily(reminder_afternoon, time=time(14, 0,  tzinfo=KYIV_TZ), name="afternoon")
    jq.run_daily(reminder_evening,   time=time(21, 0,  tzinfo=KYIV_TZ), name="evening")
    jq.run_daily(reminder_check,     time=time(21, 30, tzinfo=KYIV_TZ), name="check")
    logger.info("Ежедневные напоминания зарегистрированы (08:00, 14:00, 21:00, 21:30 Киев)")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("совет",  advice_command))
    app.add_handler(CommandHandler("итоги",  summary_command))
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
