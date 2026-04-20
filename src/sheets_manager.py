import os
import json
from datetime import datetime
from typing import Dict, List
import gspread
from google.oauth2.service_account import Credentials

class SheetsManager:
    def __init__(self):
        sheet_id = os.getenv('GOOGLE_SHEET_ID')

        scopes = ['https://www.googleapis.com/auth/spreadsheets',
                  'https://www.googleapis.com/auth/drive']

        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'config/google_credentials.json')
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Файл учётных данных Google не найден: {creds_path}")
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(sheet_id)
        
        self._ensure_sheets_exist()
    
    def _ensure_sheets_exist(self):
        """Создаёт необходимые листы, если их нет."""
        existing_titles = [ws.title for ws in self.sheet.worksheets()]
        
        required_sheets = {
            'Доходы': ['Дата', 'Сумма', 'Источник', 'Категория', 'Комментарий'],
            'Расходы': ['Дата', 'Сумма', 'Категория', 'Комментарий'],
            'Долги': ['Поставщик', 'Изначальный долг', 'Погашено', 'Остаток', 'Срок', 'Статус'],
            'Прогресс': ['Дата', 'Подушка (₽)', 'Общий долг (₽)', 'Комментарий']
        }
        
        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_titles:
                ws = self.sheet.add_worksheet(sheet_name, 1000, len(headers))
                ws.append_row(headers)
    
    def add_income(self, amount: float, description: str, category: str = "Общее"):
        """Добавить доход."""
        ws = self.sheet.worksheet('Доходы')
        today = datetime.now().strftime('%Y-%m-%d')
        ws.append_row([today, amount, description, category, ''])
    
    def add_expense(self, amount: float, category: str, comment: str = ''):
        """Добавить расход."""
        ws = self.sheet.worksheet('Расходы')
        today = datetime.now().strftime('%Y-%m-%d')
        ws.append_row([today, amount, category, comment])
    
    def add_debt(self, supplier: str, amount: float, due_date: str = ''):
        """Добавить долг."""
        ws = self.sheet.worksheet('Долги')
        
        existing_debts = ws.get_all_records()
        supplier_debt = next((d for d in existing_debts if d['Поставщик'] == supplier), None)
        
        if supplier_debt:
            row_index = existing_debts.index(supplier_debt) + 2
            current_debt = float(supplier_debt['Остаток'])
            new_debt = current_debt + amount
            ws.update_cell(row_index, 4, new_debt)
        else:
            ws.append_row([supplier, amount, 0, amount, due_date or '', 'Активен'])
    
    def pay_debt(self, supplier: str, amount: float):
        """Погасить часть долга."""
        ws = self.sheet.worksheet('Долги')
        existing_debts = ws.get_all_records()
        
        supplier_debt = next((d for d in existing_debts if d['Поставщик'] == supplier), None)
        if not supplier_debt:
            raise ValueError(f"Долг перед {supplier} не найден")
        
        row_index = existing_debts.index(supplier_debt) + 2
        current_paid = float(supplier_debt['Погашено'])
        remaining = float(supplier_debt['Остаток'])
        
        ws.update_cell(row_index, 3, current_paid + amount)
        ws.update_cell(row_index, 4, remaining - amount)
    
    def get_daily_summary(self) -> str:
        """Получить итоги за день."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        incomes_ws = self.sheet.worksheet('Доходы')
        expenses_ws = self.sheet.worksheet('Расходы')
        
        income_records = incomes_ws.get_all_records()
        expense_records = expenses_ws.get_all_records()
        
        today_income = sum(float(r['Сумма']) for r in income_records if r['Дата'] == today)
        today_expense = sum(float(r['Сумма']) for r in expense_records if r['Дата'] == today)
        
        return f"Доход: {today_income}₽\nРасход: {today_expense}₽\nБаланс: {today_income - today_expense}₽"
    
    def get_total_debt(self) -> float:
        """Получить общую сумму долгов."""
        ws = self.sheet.worksheet('Долги')
        records = ws.get_all_records()
        return sum(float(r['Остаток']) for r in records)
