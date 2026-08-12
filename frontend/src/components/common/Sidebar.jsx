import { NavLink } from 'react-router-dom';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { useAuth } from '@/hooks/authHooks/authHooks';
import { NAV_LINKS } from '@/utils/constants';
import { cn } from '@/lib/utils';

export function Sidebar() {
  const { status } = useAuth();

  if (status !== 'authenticated') return null;

  // No logo here — Navbar owns the single brand mark for the app. This rail is
  // navigation only, so it doesn't duplicate it.
  return (
    <aside className="hidden w-16 shrink-0 flex-col items-center gap-1 border-r border-sidebar-border bg-sidebar py-4 md:flex">
      <nav className="flex flex-col items-center gap-1">
        {NAV_LINKS.map(({ to, label, icon: Icon }) => (
          <Tooltip key={to}>
            <TooltipTrigger asChild>
              <NavLink
                to={to}
                aria-label={label}
                className={({ isActive }) =>
                  cn(
                    'flex size-10 items-center justify-center rounded-lg text-sidebar-foreground/70 transition-colors',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                  )
                }
              >
                <Icon className="size-4.5" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        ))}
      </nav>
    </aside>
  );
}
