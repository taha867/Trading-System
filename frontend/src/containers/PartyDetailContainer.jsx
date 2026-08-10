import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PartyStatement } from '@/components/parties/PartyStatement';
import { usePartyStatement } from '@/hooks/partyHooks/partyQueries';

export function PartyDetailContainer() {
  const { partyId } = useParams();
  const id = Number(partyId);
  const isValidId = Number.isInteger(id) && id > 0;

  const { data: statement, isLoading, isError } = usePartyStatement(isValidId ? id : undefined);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Party Statement</h1>
          <p className="mt-1 text-sm text-muted-foreground">Full ledger history and running balance for one party.</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/parties">
            <ArrowLeft />
            Back to parties
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="py-6">
          {!isValidId || isError ? (
            <p className="py-10 text-center text-destructive">Party not found.</p>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <PartyStatement statement={statement} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
