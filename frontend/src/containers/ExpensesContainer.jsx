import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { RecurringExpenseList } from '@/components/expenses/RecurringExpenseList';
import { ExpenseList } from '@/components/expenses/ExpenseList';
import { ExpenseForm } from '@/components/expenses/form/ExpenseForm';

export function ExpensesContainer() {
  const [addOpen, setAddOpen] = useState(false);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Expenses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Daily float and fixed overhead, categorized, from one screen — paid from an account the moment it's confirmed.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <Plus />
          Add expense
        </Button>
      </div>

      <RecurringExpenseList />
      <ExpenseList />

      <Sheet open={addOpen} onOpenChange={setAddOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Record expense</SheetTitle>
            <SheetDescription>Posts immediately — the account's balance drops by this amount as soon as you save.</SheetDescription>
          </SheetHeader>
          <div className="px-4">
            <ExpenseForm onSuccess={() => setAddOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
