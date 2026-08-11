import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { useAuth } from '@/hooks/authHooks/authHooks';
import { NAV_LINKS, BOTTOM_NAV_PRIMARY_PATHS, BOTTOM_NAV_MORE_ICON } from '@/utils/constants';
import { cn } from '@/lib/utils';

function TabButton({ isActive, icon: Icon, label, ...props }) {
  return (
    <button
      type="button"
      className={cn(
        'flex flex-1 flex-col items-center gap-0.5 rounded-lg py-1 text-[11px] font-medium transition-colors',
        isActive ? 'text-primary' : 'text-muted-foreground',
      )}
      {...props}
    >
      <span className={cn('flex size-8 items-center justify-center rounded-full', isActive && 'bg-primary/10')}>
        <Icon className="size-4.5" />
      </span>
      {label}
    </button>
  );
}

export function BottomNav() {
  const [moreOpen, setMoreOpen] = useState(false);
  const { status } = useAuth();
  const location = useLocation();

  if (status !== 'authenticated') return null;

  const primaryLinks = BOTTOM_NAV_PRIMARY_PATHS.map((path) => NAV_LINKS.find((link) => link.to === path)).filter(
    Boolean,
  );
  const moreLinks = NAV_LINKS.filter((link) => !BOTTOM_NAV_PRIMARY_PATHS.includes(link.to));
  const isMoreActive = moreLinks.some((link) => location.pathname.startsWith(link.to));

  return (
    <>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex items-stretch justify-around border-t bg-background/95 px-1 pt-1.5 backdrop-blur-sm md:hidden"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 0.375rem)' }}
      >
        {primaryLinks.map(({ to, label, shortLabel, icon: Icon }) => (
          <NavLink key={to} to={to} className="flex flex-1" aria-label={label}>
            {({ isActive }) => <TabButton isActive={isActive} icon={Icon} label={shortLabel ?? label} />}
          </NavLink>
        ))}
        <TabButton
          isActive={isMoreActive}
          icon={BOTTOM_NAV_MORE_ICON}
          label="More"
          aria-label="More navigation options"
          onClick={() => setMoreOpen(true)}
        />
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="rounded-t-2xl">
          <SheetHeader>
            <SheetTitle>More</SheetTitle>
            <SheetDescription className="sr-only">Additional navigation options</SheetDescription>
          </SheetHeader>
          <nav className="grid grid-cols-3 gap-3 px-4 pb-6">
            {moreLinks.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMoreOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col items-center gap-1.5 rounded-xl border p-3 text-xs font-medium transition-colors',
                    isActive
                      ? 'border-primary/40 bg-primary/5 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  )
                }
              >
                <Icon className="size-5" />
                <span className="text-center">{label}</span>
              </NavLink>
            ))}
          </nav>
        </SheetContent>
      </Sheet>
    </>
  );
}
