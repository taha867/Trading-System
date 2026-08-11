import { Users } from 'lucide-react';
import { CrudTable } from '@/components/common/CrudTable';
import { partyCrudConfig } from '@/components/parties/PartyCrudConfig';

export function PartiesContainer() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Parties</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vendors, agents, and customers — one record per contact. Only the China Vendor role is used so far;
          Customer and Local Vendor arrive in later phases without a new screen.
        </p>
      </div>
      <CrudTable
        config={partyCrudConfig}
        title="Parties"
        description="Contacts money flows to or from — roles decide where they show up."
        icon={Users}
        addLabel="Add party"
        entityLabel="party"
      />
    </div>
  );
}
