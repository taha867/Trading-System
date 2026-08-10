import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

export function FormMultiSelect({ label, error, options = [], value = [], onChange, name, disabled }) {
  const toggle = (optionValue) => {
    onChange(value.includes(optionValue) ? value.filter((v) => v !== optionValue) : [...value, optionValue]);
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label>{label}</Label>}
      <div className="flex flex-wrap gap-4">
        {options.map((option) => (
          <label
            key={option.value}
            htmlFor={`${name}-${option.value}`}
            className="flex items-center gap-2 text-sm font-normal"
          >
            <Checkbox
              id={`${name}-${option.value}`}
              checked={value.includes(option.value)}
              onCheckedChange={() => toggle(option.value)}
              disabled={disabled}
            />
            {option.label}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
