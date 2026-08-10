import { cn } from '@/lib/utils';
import { formatRMB, formatPKR } from '@/utils/currencyUtils';

export function CurrencyAmount({ value, currency = 'PKR', className }) {
  return (
    <span className={cn('font-mono tabular-nums', className)}>
      {currency === 'RMB' ? formatRMB(value) : formatPKR(value)}
    </span>
  );
}
