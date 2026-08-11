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

function GeometricShape({ className, tone }) {
  return <div className={`pointer-events-none absolute rounded-[2.5rem] border-[3px] ${tone} ${className}`} />;
}

function AuthCard({ title, description, footer, children }) {
  return (
    <div className="w-full max-w-lg">
      <div className="rounded-2xl border bg-card p-6 shadow-lg sm:p-10">
        <div className="mb-4 flex items-center gap-2.5 sm:mb-6">
          <BrandMark className="bg-primary text-primary-foreground" />
          <span className="text-lg font-semibold tracking-tight text-foreground">Trading System</span>
        </div>
        {title && <h1 className="text-xl font-semibold text-foreground">{title}</h1>}
        {description && <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>}
        <div className="mt-4 sm:mt-6">{children}</div>
      </div>
      {footer && <p className="mt-4 text-center text-sm text-muted-foreground sm:mt-6">{footer}</p>}
    </div>
  );
}

export function AuthLayout({ title, description, footer, children }) {
  return (
    <div className="flex min-h-svh flex-col lg:flex-row">
      {/* Mobile / tablet: plain centered card, no split panel */}
      <div className="flex flex-1 items-center justify-center px-4 py-6 sm:px-6 sm:py-12 lg:hidden">
        <AuthCard title={title} description={description} footer={footer}>
          {children}
        </AuthCard>
      </div>

      {/* Desktop: the split-panel composition sits as a bounded, centered island on a
          plain page background — it does not touch the browser's edges. */}
      <div className="hidden flex-1 items-center justify-center bg-muted p-3 lg:flex lg:p-4 xl:p-6">
        <div className="relative flex h-full w-full max-w-[110rem] overflow-hidden rounded-3xl shadow-2xl">
          <div className="relative w-1/2 overflow-hidden bg-background">
            <GeometricShape className="-bottom-12 -left-12 size-56 rotate-12" tone="border-primary/10" />
            <GeometricShape className="top-20 -left-10 size-24 -rotate-12 rounded-2xl" tone="border-primary/10" />
          </div>

          <div className="relative w-1/2 overflow-hidden rounded-tl-[4rem] bg-linear-to-br from-primary to-[oklch(0.3_0.14_264)] py-12 pr-10 pl-24 text-primary-foreground">
            <div
              className="pointer-events-none absolute inset-0 opacity-25"
              style={{
                backgroundImage:
                  'radial-gradient(circle at 12% 15%, white 0%, transparent 32%), radial-gradient(circle at 88% 82%, var(--gold) 0%, transparent 38%)',
              }}
            />
            <GeometricShape className="-top-10 -right-10 size-48 rotate-12" tone="border-white/10" />
            <GeometricShape className="top-20 right-20 size-20 -rotate-12 rounded-2xl" tone="border-white/10" />

            <div className="relative flex h-full flex-col">
              <div className="flex items-center gap-2.5">
                <BrandMark className="bg-white/15 backdrop-blur-sm" />
                <span className="text-lg font-semibold tracking-tight">Trading System</span>
              </div>

              <div className="flex flex-1 flex-col justify-center gap-8">
                <div className="flex flex-col gap-6">
                  <p className="text-4xl leading-[1.15] font-bold text-balance">
                    <span className="block">Run the whole trade</span>
                    <span className="block">purchase to cargo to cash</span>
                    <span className="block text-gold">from one screen.</span>
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

                <p className="text-xs text-primary-foreground/60 italic">
                  "China-to-Pakistan mobile accessories trade, one ledger at a time."
                </p>
              </div>
            </div>
          </div>

          {/* left-1/4 = the center of the white (left) panel, not the seam — this
              scales proportionally with the panel at any window width, unlike a
              fixed-pixel anchor which either hugs the seam or drifts off-center. */}
          <div className="absolute inset-y-0 left-1/4 z-10 flex -translate-x-1/2 items-center px-6">
            <AuthCard title={title} description={description} footer={footer}>
              {children}
            </AuthCard>
          </div>
        </div>
      </div>
    </div>
  );
}
