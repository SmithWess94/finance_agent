"""
Модуль агента: работа с Anthropic Claude API.
Здесь живёт вся «мозговая» логика наставника.
"""

import os
import json
from pathlib import Path
from anthropic import Anthropic

CLAUDE_MODEL = "claude-opus-4-7"
PROJECT_ROOT = Path(__file__).parent.parent


class FinanceAgent:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.system_prompt = self._load_system_prompt()

    # ─── Загрузка контекста ──────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """Собираем системный промт: роль + база знаний."""
        # Основной промт
        base = (PROJECT_ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8")

        # База знаний: все книги в knowledge_base/
        kb_dir = PROJECT_ROOT / "knowledge_base"
        books = []
        for md_file in sorted(kb_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            books.append(f"\n\n### Книга: {md_file.stem}\n{content}")

        knowledge = "\n\n---\n## БАЗА ЗНАНИЙ (принципы из книг)\n" + "".join(books)

        return base + knowledge

    # ─── Обработка сообщения пользователя ───────────────────────────

    async def process(self, user_message: str, sheets_manager, user_name: str) -> str:
        """
        Главный метод: получает сообщение, определяет намерение,
        записывает в таблицу если нужно, возвращает ответ.
        """
        # Даём Claude инструменты для записи в Sheets
        tools = [
            {
                "name": "add_income",
                "description": "Записать доход пользователя в Google Sheets",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Сумма дохода в рублях"},
                        "source": {"type": "string", "description": "Источник (продажа чая, и т.п.)"},
                        "comment": {"type": "string", "description": "Комментарий"},
                    },
                    "required": ["amount", "source"],
                },
            },
            {
                "name": "add_expense",
                "description": "Записать расход",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "category": {
                            "type": "string",
                            "enum": ["Закупка чая", "Аренда", "Реклама", "Бытовое", "Личное", "Другое"],
                        },
                        "comment": {"type": "string"},
                    },
                    "required": ["amount", "category"],
                },
            },
            {
                "name": "repay_debt",
                "description": "Записать погашение долга поставщику",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "supplier": {"type": "string"},
                        "amount": {"type": "number"},
                    },
                    "required": ["supplier", "amount"],
                },
            },
            {
                "name": "get_current_state",
                "description": "Получить текущий снимок финансов для ответа",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

        messages = [{"role": "user", "content": user_message}]

        # Первый запрос к Claude
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=self.system_prompt,
            tools=tools,
            messages=messages,
        )

        # Обрабатываем tool_use если есть
        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input, sheets_manager)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=self.system_prompt,
                tools=tools,
                messages=messages,
            )

        # Извлекаем финальный текст
        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(text_parts) or "Готово ✅"

    def _execute_tool(self, name: str, args: dict, sheets) -> dict:
        """Вызов инструмента: запись в Google Sheets."""
        if name == "add_income":
            return sheets.add_income(**args)
        elif name == "add_expense":
            return sheets.add_expense(**args)
        elif name == "repay_debt":
            return sheets.repay_debt(**args)
        elif name == "get_current_state":
            return sheets.get_snapshot()
        return {"error": f"Неизвестный инструмент: {name}"}

    # ─── Запланированные сообщения ──────────────────────────────────

    async def morning_message(self, snapshot: dict) -> str:
        prompt = (
            f"Сейчас 08:00, утро. Контекст: {snapshot}. "
            f"Напиши короткое тёплое утреннее сообщение пользователю, "
            f"с вопросом про план на день и заработок. 2-3 строки максимум."
        )
        return await self._quick_gen(prompt)

    async def midday_message(self, snapshot: dict) -> str:
        prompt = (
            f"Сейчас 14:00, середина дня. Контекст: {snapshot}. "
            f"Мягко поинтересуйся как идут дела, напомни фиксировать операции. 2 строки."
        )
        return await self._quick_gen(prompt)

    async def evening_message(self, snapshot: dict) -> str:
        prompt = (
            f"Сейчас 21:00, вечер. Контекст: {snapshot}. "
            f"Попроси подвести итоги дня: доходы, расходы. "
            f"Если прогресс хороший — похвали. 3-4 строки."
        )
        return await self._quick_gen(prompt)

    async def format_report(self, report: dict) -> str:
        prompt = f"Оформи этот отчёт красиво для Telegram: {report}"
        return await self._quick_gen(prompt)

    async def format_debts(self, debts: list) -> str:
        prompt = f"Покажи список долгов пользователю с комментарием: {debts}"
        return await self._quick_gen(prompt)

    async def give_advice(self, context_data: dict) -> str:
        prompt = (
            f"Дай совет на основе текущей ситуации: {context_data}. "
            f"Опирайся на принципы из книг в базе знаний. "
            f"Один конкретный, применимый совет."
        )
        return await self._quick_gen(prompt)

    async def _quick_gen(self, user_prompt: str) -> str:
        """Быстрая генерация без инструментов."""
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "\n".join(b.text for b in response.content if hasattr(b, "text"))
