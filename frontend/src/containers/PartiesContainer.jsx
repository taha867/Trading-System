import { Users, HandCoins, Landmark } from 'lucide-react';
import { CrudTable } from '@/components/common/CrudTable';
import { StatCard } from '@/components/common/StatCard';
import { partyCrudConfig } from '@/components/parties/PartyCrudConfig';

function PartiesSummary(data) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <StatCard icon={Users} label="Parties" value={data.total} format="count" />
      <StatCard icon={HandCoins} label="Total receivable" value={data.total_receivable_pkr} />
      <StatCard icon={Landmark} label="Total payable" value={data.total_payable_pkr} />
    </div>
  );
}

export function PartiesContainer() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Parties</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vendors, agents, and customers — one record per contact. Search by name or filter by role to find one
          quickly.
        </p>
      </div>
      <CrudTable
        config={partyCrudConfig}
        title="Parties"
        description="Contacts money flows to or from — roles decide where they show up."
        icon={Users}
        addLabel="Add party"
        entityLabel="party"
        renderSummary={PartiesSummary}
      />
    </div>
  );
}
