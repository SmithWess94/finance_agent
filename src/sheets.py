"""
Модуль для работы с Google Sheets через gspread.
Все операции чтения/записи финансовых данных.
"""

import os
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

INCOME_SHEET = "Доходы"
EXPENSE_SHEET = "Расходы"
DEBTS_SHEET = "Долги поставщикам"
GOALS_SHEET = "Цели и прогресс"


class SheetsManager:
    def __init__(self):
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/google_credentials.json")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")

        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(sheet_id)

    # ─── Запись операций ────────────────────────────────────────────

    def add_income(self, amount: float, source: str, comment: str = "") -> dict:
        ws = self.spreadsheet.worksheet(INCOME_SHEET)
        today = datetime.now().strftime("%Y-%m-%d")
        ws.append_row([today, amount, source, "Продажи", comment])
        return {"status": "ok", "added": {"amount": amount, "source": source, "date": today}}

    def add_expense(self, amount: float, category: str, comment: str = "") -> dict:
        ws = self.spreadsheet.worksheet(EXPENSE_SHEET)
        today = datetime.now().strftime("%Y-%m-%d")
        ws.append_row([today, amount, category, comment])
        return {"status": "ok", "added": {"amount": amount, "category": category, "date": today}}

    def repay_debt(self, supplier: str, amount: float) -> dict:
        ws = self.spreadsheet.worksheet(DEBTS_SHEET)
        records = ws.get_all_records()

        for i, row in enumerate(records, start=2):
            if row.get("Поставщик", "").lower() == supplier.lower():
                repaid = float(row.get("Погашено", 0) or 0) + amount
                initial = float(row.get("Изначальный долг", 0) or 0)
                remaining = initial - repaid
                status = "Закрыт" if remaining <= 0 else "Активен"

                ws.update_cell(i, 3, repaid)       # колонка "Погашено"
                ws.update_cell(i, 4, remaining)    # колонка "Остаток"
                ws.update_cell(i, 6, status)       # колонка "Статус"

                return {
                    "status": "ok",
                    "supplier": supplier,
                    "repaid_total": repaid,
                    "remaining": remaining,
                }

        # Если поставщика не было — создаём
        ws.append_row([supplier, amount, amount, 0, "", "Закрыт"])
        return {"status": "ok", "supplier": supplier, "note": "новый поставщик, долг сразу закрыт"}

    # ─── Чтение ─────────────────────────────────────────────────────

    def has_records_today(self) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        income = self.spreadsheet.worksheet(INCOME_SHEET).get_all_records()
        expense = self.spreadsheet.worksheet(EXPENSE_SHEET).get_all_records()
        for row in income + expense:
            if str(row.get("Дата", "")).startswith(today):
                return True
        return False

    def get_report(self, period: str = "day") -> dict:
        """period: day / week / month"""
        today = datetime.now().date()
        if period == "day":
            since = today
        elif period == "week":
            since = today - timedelta(days=7)
        else:
            since = today - timedelta(days=30)

        income_ws = self.spreadsheet.worksheet(INCOME_SHEET).get_all_records()
        expense_ws = self.spreadsheet.worksheet(EXPENSE_SHEET).get_all_records()

        total_income = sum(
            float(r.get("Сумма", 0) or 0)
            for r in income_ws
            if self._parse_date(r.get("Дата")) >= since
        )
        total_expense = sum(
            float(r.get("Сумма", 0) or 0)
            for r in expense_ws
            if self._parse_date(r.get("Дата")) >= since
        )

        return {
            "period": period,
            "income": total_income,
            "expense": total_expense,
            "net": total_income - total_expense,
        }

    def get_debts(self) -> list:
        ws = self.spreadsheet.worksheet(DEBTS_SHEET)
        return ws.get_all_records()

    def get_snapshot(self) -> dict:
        """Краткая сводка — передаётся агенту как контекст."""
        day = self.get_report("day")
        week = self.get_report("week")
        debts = self.get_debts()
        total_debt = sum(float(d.get("Остаток", 0) or 0) for d in debts if d.get("Статус") == "Активен")

        return {
            "today": day,
            "week": week,
            "total_debt": total_debt,
            "active_debts_count": len([d for d in debts if d.get("Статус") == "Активен"]),
        }

    @staticmethod
    def _parse_date(date_str) -> datetime.date:
        if not date_str:
            return datetime.min.date()
        try:
            return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
        except ValueError:
            return datetime.min.date()
