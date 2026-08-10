from typing import Literal

ExpenseCategoryFrequency = Literal["daily", "monthly"]

# Manual entries (service.create_expense) go straight to "confirmed" — money already moved.
# Recurring-template-generated entries (service.generate_expense_from_template) start at
# "draft" and only reach "confirmed" via service.confirm_expense, which is the only status
# transition this domain has.
ExpenseStatus = Literal["draft", "confirmed"]
