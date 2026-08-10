import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

export function FormField({ label, error, className, ...fieldProps }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label htmlFor={fieldProps.name}>{label}</Label>}
      <Input
        id={fieldProps.name}
        className={cn(error && 'border-destructive', className)}
        {...fieldProps}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
