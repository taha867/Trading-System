import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { cn } from '@/lib/utils';

// format="currency" (default) renders `value` as PKR via CurrencyAmount;
// format="count" renders it as a plain number, for tiles that show a row
// count rather than a money amount (e.g. "Parties: 21").
// valueClassName tints the value (e.g. "text-destructive" for a loss).
export function StatCard({ icon: Icon, label, value, format = 'currency', valueClassName }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border p-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="size-5" />
      </span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={cn('text-2xl font-semibold text-foreground', valueClassName)}>
          {format === 'count' ? value : <CurrencyAmount value={value} />}
        </p>
      </div>
    </div>
  );
}
