import { Badge } from '@/components/ui/badge';
import { PARTY_ROLE_OPTIONS } from '@/utils/constants';

const LABEL_BY_VALUE = Object.fromEntries(PARTY_ROLE_OPTIONS.map((o) => [o.value, o.label]));

export function PartyRoleBadges({ roles = [] }) {
  if (roles.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {roles.map((role) => (
        <Badge key={role} variant="secondary">
          {LABEL_BY_VALUE[role] ?? role}
        </Badge>
      ))}
    </div>
  );
}
