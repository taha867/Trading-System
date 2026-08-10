import { useAuth } from '@/hooks/authHooks/authHooks';

export function Footer() {
  const { status } = useAuth();

  if (status !== 'authenticated') return null;

  return (
    <footer className="border-t px-4 py-4 text-center text-xs text-muted-foreground">
      Trading System · China-to-Pakistan mobile accessories trade
    </footer>
  );
}
