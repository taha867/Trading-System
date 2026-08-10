import { Link } from 'react-router-dom';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { useCreateParty, useUpdateParty, useDeactivateParty } from '@/hooks/partyHooks/partyMutations';
import { partyCreateSchema, partyUpdateSchema } from '@/validations/partySchemas';
import { partyKeys } from '@/utils/queryKeys';
import { PARTY_ROLE_OPTIONS } from '@/utils/constants';
import { PartyRoleBadges } from '@/components/parties/PartyRoleBadges';

export const partyCrudConfig = {
  queryKey: partyKeys,
  useList: useParties,
  useCreate: useCreateParty,
  useUpdate: useUpdateParty,
  // Exported hook is named per CLAUDE.md's convention (useDeactivateParty); the
  // config key stays useDelete to match CrudTable's generic interface.
  useDelete: useDeactivateParty,
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
