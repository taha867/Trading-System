import { useState } from 'react';
import { ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '@/components/ui/command';
import { cn } from '@/lib/utils';

export function FormCombobox({
  label,
  error,
  options = [],
  value,
  onChange,
  name,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyLabel = 'No results.',
  disabled,
  // Opt-in server-search mode: pass inputValue/onInputValueChange to observe
  // what's typed (debounce it, call a search-filtered query hook) instead of
  // relying on cmdk's own client-side filter over a pre-fetched `options`
  // list — needed once an entity is too large to fetch in full (Items,
  // Models, ...). Omit both for the default static-options behavior, used by
  // every small fixed lookup-table picker (Category, CargoMode, ...).
  inputValue,
  onInputValueChange,
  loading = false,
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value);
  const serverSearch = onInputValueChange !== undefined;

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label htmlFor={name}>{label}</Label>}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={name}
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              'w-full justify-between font-normal',
              !selected && 'text-muted-foreground',
              error && 'border-destructive',
            )}
          >
            {selected ? selected.label : placeholder}
            <ChevronsUpDown className="opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
          <Command shouldFilter={!serverSearch}>
            <CommandInput
              placeholder={searchPlaceholder}
              value={serverSearch ? inputValue : undefined}
              onValueChange={serverSearch ? onInputValueChange : undefined}
            />
            <CommandList>
              <CommandEmpty>{loading ? 'Searching…' : emptyLabel}</CommandEmpty>
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option.value}
                    value={option.label}
                    data-checked={option.value === value}
                    onSelect={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                  >
                    {option.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
