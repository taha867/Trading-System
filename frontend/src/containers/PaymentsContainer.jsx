import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { PaymentAccountList } from '@/components/payments/PaymentAccountList';
import { PaymentTransactionList } from '@/components/payments/PaymentTransactionList';
import { PaymentForm } from '@/components/payments/form/PaymentForm';

export function PaymentsContainer() {
  const [recordOpen, setRecordOpen] = useState(false);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Payments</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every rupee tied to an account — record a payment and its account and party balance move together.
          </p>
        </div>
        <Button onClick={() => setRecordOpen(true)}>
          <Plus />
          Record payment
        </Button>
      </div>

      <PaymentAccountList />
      <PaymentTransactionList />

      <Sheet open={recordOpen} onOpenChange={setRecordOpen}>
        <SheetContent className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Record payment</SheetTitle>
            <SheetDescription>Money in or out, tied to an account and — optionally — a party.</SheetDescription>
          </SheetHeader>
          <div className="px-4">
            <PaymentForm onSuccess={() => setRecordOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
