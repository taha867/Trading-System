import { useState } from 'react';
import { ArrowLeftRight, LogOut } from 'lucide-react';
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

export function Navbar() {
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
      <div className="flex items-center justify-between gap-4 px-4 py-3 md:px-6">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ArrowLeftRight className="size-4" />
          </span>
          <span className="font-semibold tracking-tight text-foreground">Trading System</span>
        </div>

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
      </div>

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
