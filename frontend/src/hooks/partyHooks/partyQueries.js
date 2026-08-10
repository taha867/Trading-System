import { useQuery } from '@tanstack/react-query';
import { partyKeys } from '@/utils/queryKeys';
import { listParties, getPartyStatement } from '@/services/partyService';
import { PARTY_ROLE } from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 100 };

export function useParties(params) {
  return useQuery({
    queryKey: partyKeys.list(params),
    queryFn: () => listParties(params),
  });
}

// Derived, not a separate backend call — GET /parties has no role filter, so this
// filters the one fetched page client-side (phase-1-frontend spec §2.1/§5.5).
export function useChinaVendorParties() {
  const query = useParties(LOOKUP_PAGE);
  const vendors = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CHINA_VENDOR));
  return { ...query, vendors };
}

// Same client-side role-filter pattern as useChinaVendorParties, for the cargo
// shipment form's agent picker (phase-2-frontend spec §5).
export function useCargoAgentParties() {
  const query = useParties(LOOKUP_PAGE);
  const agents = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CARGO_AGENT));
  return { ...query, agents };
}

// Same client-side role-filter pattern as useChinaVendorParties/useCargoAgentParties,
// for the sales order form's customer picker (phase-4-frontend spec §6.2).
export function useCustomerParties() {
  const query = useParties(LOOKUP_PAGE);
  const customers = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.CUSTOMER));
  return { ...query, customers };
}

// Same client-side role-filter pattern as useChinaVendorParties/useCargoAgentParties/
// useCustomerParties, for the local vendor path of the purchase order form
// (phase-5-frontend spec §5.1).
export function useLocalVendorParties() {
  const query = useParties(LOOKUP_PAGE);
  const vendors = (query.data?.items ?? []).filter((party) => party.roles.includes(PARTY_ROLE.LOCAL_VENDOR));
  return { ...query, vendors };
}

export function usePartyStatement(id) {
  return useQuery({
    queryKey: partyKeys.statement(id),
    queryFn: () => getPartyStatement(id),
    enabled: Boolean(id),
  });
}
