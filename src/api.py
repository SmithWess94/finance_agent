import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.bot import (
    FinanceAdvisor, advisor, sheets_manager, TELEGRAM_BOT_TOKEN,
    reminder_morning, reminder_afternoon, reminder_evening, reminder_check,
    advice_command, KYIV_TZ,
)

load_dotenv()

WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')
logger = logging.getLogger(__name__)

mini_app_advisor = FinanceAdvisor()


# ── Pydantic models ──────────────────────────────────────────────────────────

class IncomeReq(BaseModel):
    amount: float
    description: str

class ExpenseReq(BaseModel):
    amount: float
    category: str

class RepayReq(BaseModel):
    supplier: str
    amount: float

class ChatReq(BaseModel):
    message: str


# ── Telegram handlers ────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_url = f"{WEBHOOK_URL}/app/"
    text = "Привет! 👋\n\nЯ твой финансовый помощник. Помогу вести учёт, планировать бюджет и разобраться с долгами.\n\nПиши обычным текстом или открой дашборд:"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Открыть дашборд", web_app=WebAppInfo(url=app_url))
    ]])
    await update.message.reply_text(text, reply_markup=keyboard)


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_url = f"{WEBHOOK_URL}/app/"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Открыть дашборд", web_app=WebAppInfo(url=app_url))
    ]])
    await update.message.reply_text("Твой финансовый дашборд:", reply_markup=keyboard)


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats = await asyncio.to_thread(sheets_manager.get_daily_summary)
        response = await asyncio.to_thread(advisor.chat, f"Вот мой отчёт за день: {stats}")
        await update.message.reply_text(f"📊 Итоги дня:\n{stats}\n\n{response}")
    except Exception as e:
        logger.error(f"summary error: {e}")
        await update.message.reply_text("Ошибка при получении отчёта")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = await asyncio.to_thread(advisor.chat, update.message.text)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"message error: {e}")
        await update.message.reply_text("Произошла ошибка")


# ── App lifecycle ────────────────────────────────────────────────────────────

ptb_app: Application = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app
    ptb_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    ptb_app.add_handler(CommandHandler("start",  start_handler))
    ptb_app.add_handler(CommandHandler("menu",   menu_handler))
    ptb_app.add_handler(CommandHandler("summary", summary_handler))
    ptb_app.add_handler(CommandHandler("совет",  advice_command))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    await ptb_app.initialize()

    jq = ptb_app.job_queue
    if jq:
        jq.run_daily(reminder_morning,   time=time(8,  0,  tzinfo=KYIV_TZ), name="morning")
        jq.run_daily(reminder_afternoon, time=time(14, 0,  tzinfo=KYIV_TZ), name="afternoon")
        jq.run_daily(reminder_evening,   time=time(21, 0,  tzinfo=KYIV_TZ), name="evening")
        jq.run_daily(reminder_check,     time=time(21, 30, tzinfo=KYIV_TZ), name="check")
        logger.info("Напоминания зарегистрированы (08:00, 14:00, 21:00, 21:30 Киев)")

    if WEBHOOK_URL:
        await ptb_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        logger.info(f"Webhook set: {WEBHOOK_URL}/webhook")
    else:
        logger.warning("WEBHOOK_URL not set — webhook not registered")
    await ptb_app.start()

    yield

    await ptb_app.stop()
    await ptb_app.shutdown()


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/app", StaticFiles(directory="mini_app", html=True), name="mini_app")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"ok": True}


@app.get("/api/snapshot")
async def api_snapshot():
    try:
        return await asyncio.to_thread(sheets_manager.get_snapshot)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/debts")
async def api_debts():
    try:
        return await asyncio.to_thread(sheets_manager.get_debts)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/income")
async def api_income(req: IncomeReq):
    try:
        await asyncio.to_thread(sheets_manager.add_income, req.amount, req.description)
        return {"ok": True, "message": f"Доход {req.amount:,.0f}₴ записан"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/expense")
async def api_expense(req: ExpenseReq):
    try:
        await asyncio.to_thread(sheets_manager.add_expense, req.amount, req.category)
        return {"ok": True, "message": f"Расход {req.amount:,.0f}₴ записан"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/repay")
async def api_repay(req: RepayReq):
    try:
        await asyncio.to_thread(sheets_manager.pay_debt, req.supplier, req.amount)
        return {"ok": True, "message": f"Платёж {req.amount:,.0f}₴ поставщику {req.supplier} записан"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/chat")
async def api_chat(req: ChatReq):
    try:
        response = await asyncio.to_thread(mini_app_advisor.chat, req.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(500, str(e))
