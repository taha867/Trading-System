import { ArrowLeftRight } from 'lucide-react';

const HIGHLIGHTS = [
  'One ledger for every rupee and every unit of stock',
  'RMB → PKR rates snapshotted, never recalculated',
  'Built for how a China-to-Pakistan trading floor actually runs',
];

function BrandMark({ className }) {
  return (
    <span className={`flex size-9 items-center justify-center rounded-lg ${className}`}>
      <ArrowLeftRight className="size-5" />
    </span>
  );
}

export function AuthLayout({ title, description, footer, children }) {
  return (
    <div className="flex min-h-svh flex-col lg:flex-row">
      <div className="relative hidden overflow-hidden bg-linear-to-br from-primary to-[oklch(0.3_0.14_264)] px-10 py-12 text-primary-foreground lg:flex lg:w-1/2 lg:flex-col lg:justify-between xl:w-3/5">
        <div
          className="pointer-events-none absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              'radial-gradient(circle at 12% 15%, white 0%, transparent 32%), radial-gradient(circle at 88% 82%, var(--gold) 0%, transparent 38%)',
          }}
        />
        <div className="relative flex items-center gap-2.5">
          <BrandMark className="bg-white/15 backdrop-blur-sm" />
          <span className="text-lg font-semibold tracking-tight">Trading System</span>
        </div>

        <div className="relative flex flex-col gap-6">
          <p className="text-3xl leading-tight font-semibold text-balance">
            Run the whole trade — purchase to cargo to cash — from one screen.
          </p>
          <ul className="flex flex-col gap-3">
            {HIGHLIGHTS.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-sm text-primary-foreground/85">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-gold" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-primary-foreground/60">
          China-to-Pakistan mobile accessories trade, one ledger at a time.
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <BrandMark className="bg-primary text-primary-foreground" />
            <span className="text-lg font-semibold tracking-tight text-foreground">Trading System</span>
          </div>

          <div className="rounded-xl border bg-card p-6 shadow-sm sm:p-8">
            {title && <h1 className="text-xl font-semibold text-foreground">{title}</h1>}
            {description && <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>}
            <div className="mt-6">{children}</div>
          </div>

          {footer && <p className="mt-6 text-center text-sm text-muted-foreground">{footer}</p>}
        </div>
      </div>
    </div>
  );
}
