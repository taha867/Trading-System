import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { shiftMonth } from '@/utils/dateUtils';

const MODES = [
  { value: 'month', label: 'Month' },
  { value: 'range', label: 'Date range' },
  { value: 'all', label: 'All dates' },
];

// The one date filter for list / report screens: a month (with prev / next), a From – To range (year, month and day),
// or all dates. Controlled by useDateFilter(): pass its return value as `filter`. Stacks on a phone.
export function DateFilter({ filter, id = 'date', className, label = 'Dates', modes = ['month', 'range', 'all'] }) {
  const { mode, month, from, to } = filter;
  const inverted = mode === 'range' && from && to && from > to;
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label htmlFor={`${id}_${mode}`}>{label}</Label>
      <div role="group" aria-label="Date filter type" className="flex flex-wrap gap-1">
        {MODES.filter((option) => modes.includes(option.value)).map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={mode === option.value ? 'default' : 'outline'}
            aria-pressed={mode === option.value}
            onClick={() => filter.setMode(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
      {mode === 'month' && (
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="icon" aria-label="Previous month" onClick={() => filter.setMonth(shiftMonth(month, -1))}>
            <ChevronLeft />
          </Button>
          <Input id={`${id}_month`} type="month" value={month} onChange={(event) => filter.setMonth(event.target.value)} />
          <Button type="button" variant="outline" size="icon" aria-label="Next month" onClick={() => filter.setMonth(shiftMonth(month, 1))}>
            <ChevronRight />
          </Button>
        </div>
      )}
      {mode === 'range' && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`${id}_range`} className="text-xs font-normal text-muted-foreground">
              From
            </Label>
            <Input id={`${id}_range`} type="date" value={from} max={to || undefined} onChange={(event) => filter.setRange({ from: event.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor={`${id}_to`} className="text-xs font-normal text-muted-foreground">
              To
            </Label>
            <Input id={`${id}_to`} type="date" value={to} min={from || undefined} onChange={(event) => filter.setRange({ to: event.target.value })} />
          </div>
          {inverted && <p className="text-xs text-destructive sm:col-span-2">From must be on or before To.</p>}
        </div>
      )}
      {mode === 'all' && <p className="text-xs text-muted-foreground">Showing every date.</p>}
    </div>
  );
}
