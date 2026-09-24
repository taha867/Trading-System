import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useCreateParty, useUpdateParty, useDeactivateParty } from '@/hooks/partyHooks/partyMutations';
import { partyCreateSchema, partyUpdateSchema } from '@/validations/partySchemas';
import { partyKeys } from '@/utils/queryKeys';
import { PARTY_ROLE_OPTIONS } from '@/utils/constants';
import { PartyRoleBadges } from '@/components/parties/PartyRoleBadges';

// Sign convention per backend spec §2.6 (same as PartyStatement.jsx): positive
// balance_pkr means the party owes the business (receivable); negative means
// the business owes the party (payable).
function balanceLabel(value) {
  const num = Number(value);
  if (num > 0) return 'Owes us';
  if (num < 0) return 'We owe them';
  return 'Settled';
}

export const partyCrudConfig = {
  queryKey: partyKeys,
  useList: useParties,
  useCreate: useCreateParty,
  useUpdate: useUpdateParty,
  // Exported hook is named per CLAUDE.md's convention (useDeactivateParty); the
  // config key stays useDelete to match CrudTable's generic interface.
  useDelete: useDeactivateParty,
  filters: [
    { key: 'search', label: 'Name', component: 'search', placeholder: 'Search parties…' },
    { key: 'role', label: 'Role', options: PARTY_ROLE_OPTIONS },
  ],
  columns: [
    {
      key: 'name',
      label: 'Name',
      render: (row) => (
        <Link to={`/parties/${row.id}`} className="font-medium text-primary hover:underline">
          {row.name}
        </Link>
      ),
    },
    { key: 'roles', label: 'Roles', render: (row) => <PartyRoleBadges roles={row.roles} /> },
    { key: 'contact', label: 'Contact' },
    {
      key: 'balance_pkr',
      label: 'Balance',
      render: (row) => (
        <div className="flex items-center justify-end gap-2 text-right">
          <CurrencyAmount value={row.balance_pkr} className="font-medium text-foreground" />
          <Badge variant={Number(row.balance_pkr) >= 0 ? 'secondary' : 'destructive'} className="whitespace-nowrap">
            {balanceLabel(row.balance_pkr)}
          </Badge>
        </div>
      ),
    },
  ],
  createSchema: partyCreateSchema,
  updateSchema: partyUpdateSchema,
  fields: [
    { name: 'name', label: 'Party name', component: 'text' },
    { name: 'contact', label: 'Contact', component: 'text' },
    { name: 'address', label: 'Address', component: 'text' },
    { name: 'roles', label: 'Roles', component: 'multiselect', options: PARTY_ROLE_OPTIONS, defaultValue: [] },
    // opening_balance is write-once on the backend — disabled in edit mode.
    {
      name: 'opening_balance',
      label: 'Opening balance',
      component: 'number',
      step: '0.01',
      defaultValue: 0,
      editableOnUpdate: false,
    },
  ],
};
