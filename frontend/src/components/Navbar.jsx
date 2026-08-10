import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Menu, X, ArrowLeftRight, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { useAuth } from '@/hooks/authHooks/authHooks';
import { useSignOut } from '@/hooks/authHooks/authMutations';
import { getInitials } from '@/utils/stringUtils';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/purchase-orders', label: 'Purchase Orders' },
  { to: '/cargo-shipments', label: 'Cargo Shipments' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/sales-orders', label: 'Sales Orders' },
  { to: '/payments', label: 'Payments' },
  { to: '/expenses', label: 'Expenses' },
  { to: '/parties', label: 'Parties' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/settings', label: 'Settings' },
];

function NavItem({ to, label, onClick, className }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
          isActive
            ? 'bg-accent text-accent-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          className,
        )
      }
    >
      {label}
    </NavLink>
  );
}

export function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [confirmSignOutOpen, setConfirmSignOutOpen] = useState(false);
  const { status, user } = useAuth();
  const signOut = useSignOut();

  if (status !== 'authenticated') return null;

  const openSignOutConfirm = () => {
    setConfirmSignOutOpen(true);
  };

  const confirmSignOut = () => {
    setConfirmSignOutOpen(false);
    signOut();
  };

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ArrowLeftRight className="size-4" />
          </span>
          <span className="font-semibold tracking-tight text-foreground">Trading System</span>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <NavItem key={link.to} to={link.to} label={link.label} />
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                aria-label={`Account menu for ${user?.username ?? 'current user'}`}
              >
                <Avatar>
                  <AvatarFallback>{getInitials(user?.username)}</AvatarFallback>
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {user?.username && (
                <>
                  <DropdownMenuLabel>
                    Signed in as <span className="font-medium text-foreground">{user.username}</span>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onSelect={openSignOutConfirm}>
                <LogOut />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            variant="ghost"
            size="icon-sm"
            className="md:hidden"
            onClick={() => setIsOpen((open) => !open)}
            aria-label="Toggle navigation menu"
          >
            {isOpen ? <X /> : <Menu />}
          </Button>
        </div>
      </div>

      {isOpen && (
        <nav className="flex flex-col gap-1 border-t px-4 py-3 md:hidden">
          {NAV_LINKS.map((link) => (
            <NavItem key={link.to} to={link.to} label={link.label} onClick={() => setIsOpen(false)} className="w-full" />
          ))}
        </nav>
      )}

      <ConfirmDialog
        open={confirmSignOutOpen}
        onOpenChange={setConfirmSignOutOpen}
        onConfirm={confirmSignOut}
        title="Sign out?"
        description="You'll need to sign in again to get back to Settings."
        confirmLabel="Sign out"
      />
    </header>
  );
}
