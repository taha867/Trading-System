from src.exceptions import NotFoundException


class ExpenseNotFound(NotFoundException):
    detail = "Expense not found"


class RecurringExpenseTemplateNotFound(NotFoundException):
    detail = "Recurring expense template not found"
