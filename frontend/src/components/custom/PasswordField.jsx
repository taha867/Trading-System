import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

export function PasswordField({ label, error, className, ...fieldProps }) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label htmlFor={fieldProps.name}>{label}</Label>}
      <div className="relative">
        <Input
          id={fieldProps.name}
          type={showPassword ? 'text' : 'password'}
          className={cn('pr-9', error && 'border-destructive', className)}
          {...fieldProps}
        />
        <button
          type="button"
          onClick={() => setShowPassword((show) => !show)}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground outline-none hover:text-foreground focus-visible:text-foreground"
          aria-label={showPassword ? 'Hide password' : 'Show password'}
        >
          {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
