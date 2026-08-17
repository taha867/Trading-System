import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect, FormMultiSelect } from '@/components/custom';
import { cargoShipmentCreateSchema } from '@/validations/cargoSchemas';
import { useCreateCargoShipment } from '@/hooks/cargoHooks/cargoMutations';
import { useCargoModes, useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import { useCargoAgentParties, useParties } from '@/hooks/partyHooks/partyQueries';
import { useDraftPurchaseOrders } from '@/hooks/purchasingHooks/purchasingQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useCategories } from '@/hooks/catalogHooks/categoryQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { CARGO_COST_BASIS_CODE } from '@/utils/constants';
import { toMoney, computeCargoAllocation, formatPKR } from '@/utils/currencyUtils';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function CargoShipmentForm({ onSuccess }) {
  const { agents } = useCargoAgentParties();
  const { data: modesData } = useCargoModes(LOOKUP_PAGE);
  const { data: costBasesData } = useCargoCostBases(LOOKUP_PAGE);
  const { draftOrders } = useDraftPurchaseOrders();
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  const { data: categoriesData } = useCategories(LOOKUP_PAGE);
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const vendorNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const itemById = Object.fromEntries((itemsData?.items ?? []).map((i) => [i.id, i]));
  const categoryNameById = Object.fromEntries((categoriesData?.items ?? []).map((c) => [c.id, c.name]));
  const modelNameById = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.name]));

  function lineLabel(line) {
    const item = itemById[line.item_id];
    if (!item) return `Item #${line.item_id}`;
    const parts = [modelNameById[item.model_id], categoryNameById[item.category_id], item.sku].filter(Boolean);
    return parts.join(' · ') + (item.variant ? ` (${item.variant})` : '');
  }

  const agentOptions = agents.map((a) => ({ value: String(a.id), label: a.name }));
  const modeOptions = (modesData?.items ?? []).map((m) => ({ value: String(m.id), label: m.name }));
  const costBasisOptions = (costBasesData?.items ?? []).map((b) => ({ value: String(b.id), label: b.name }));
  const poOptions = draftOrders.map((po) => ({
    value: String(po.id),
    label: `#${po.id} · ${vendorNameById[po.party_id] ?? `Party #${po.party_id}`} · ${po.order_date} · ${po.lines.length} line(s)`,
  }));

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(cargoShipmentCreateSchema, {}, { raw: true }),
    defaultValues: {
      cargo_agent_id: '',
      cargo_mode_id: '',
      cost_basis_id: '',
      shipment_date: todayIso(),
      total_cost_pkr: '',
      purchase_order_ids: [],
      basisValues: {},
    },
  });
  const createMutation = useCreateCargoShipment();

  const selectedPoIds = (watch('purchase_order_ids') ?? []).map(Number);
  const costBasisId = watch('cost_basis_id');
  const totalCostPkr = watch('total_cost_pkr');
  const basisValues = watch('basisValues') ?? {};

  const selectedCostBasis = (costBasesData?.items ?? []).find((b) => String(b.id) === String(costBasisId));
  const isPieceBasis = selectedCostBasis?.code === CARGO_COST_BASIS_CODE.PIECE;

  const selectedLines = draftOrders
    .filter((po) => selectedPoIds.includes(po.id))
    .flatMap((po) => po.lines.map((line) => ({ ...line, poId: po.id })));

  // Piece basis derives its figure from each line's own qty — never user-entered; the
  // backend rejects any line_basis_values entries at all when code === "piece".
  const effectiveBasisValues = isPieceBasis
    ? Object.fromEntries(selectedLines.map((l) => [l.id, l.qty]))
    : basisValues;

  const missingBasisValues =
    !isPieceBasis &&
    Boolean(selectedCostBasis) &&
    selectedLines.some((l) => !effectiveBasisValues[l.id] || Number(effectiveBasisValues[l.id]) <= 0);

  const allocationPreview =
    selectedCostBasis && totalCostPkr && !missingBasisValues
      ? computeCargoAllocation({ lines: selectedLines, basisValues: effectiveBasisValues, totalCostPkr })
      : {};

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        cargo_agent_id: values.cargo_agent_id,
        cargo_mode_id: values.cargo_mode_id,
        cost_basis_id: values.cost_basis_id,
        shipment_date: values.shipment_date,
        total_cost_pkr: values.total_cost_pkr,
        purchase_order_ids: values.purchase_order_ids,
        line_basis_values: isPieceBasis
          ? []
          : selectedLines.map((l) => ({
              purchase_order_line_id: l.id,
              basis_value: values.basisValues?.[l.id] ?? '',
            })),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch, a PO
      // that got allocated by someone else since this form's data was fetched, a
      // missing basis figure) — keep the form open to fix and retry, same pattern
      // as PurchaseOrderForm.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller
          name="cargo_agent_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Cargo agent"
              placeholder="Select an agent"
              options={agentOptions}
              error={errors.cargo_agent_id?.message}
            />
          )}
        />
        <Controller
          name="shipment_date"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="date" label="Shipment date" error={errors.shipment_date?.message} />
          )}
        />
        <Controller
          name="cargo_mode_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Cargo mode"
              placeholder="Sea or Air"
              options={modeOptions}
              error={errors.cargo_mode_id?.message}
            />
          )}
        />
        <Controller
          name="cost_basis_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Cost basis"
              placeholder="Weight, CBM, or Piece"
              options={costBasisOptions}
              error={errors.cost_basis_id?.message}
            />
          )}
        />
        <Controller
          name="total_cost_pkr"
          control={control}
          render={({ field }) => (
            <FormField
              {...field}
              type="number"
              step="0.01"
              label="Total freight cost (PKR)"
              error={errors.total_cost_pkr?.message}
            />
          )}
        />
      </div>

      <Controller
        name="purchase_order_ids"
        control={control}
        render={({ field }) => (
          <FormMultiSelect
            {...field}
            label="Attach open purchase orders"
            options={poOptions}
            error={errors.purchase_order_ids?.message}
          />
        )}
      />
      {poOptions.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No draft purchase orders are open to attach — every PO has already been allocated to a shipment.
        </p>
      )}

      {selectedLines.length > 0 && selectedCostBasis && (
        <div className="flex flex-col gap-3 rounded-lg border p-3">
          <p className="text-sm font-medium text-foreground">
            Split {formatPKR(toMoney(totalCostPkr || 0))} across {selectedLines.length} line(s) by{' '}
            {selectedCostBasis.name}
          </p>
          {selectedLines.map((line) => (
            <div key={line.id} className="grid gap-3 md:grid-cols-[2fr_1fr_1fr_1fr] md:items-center">
              <span className="text-sm">
                PO #{line.poId} — {lineLabel(line)} · qty {line.qty}
              </span>
              {isPieceBasis ? (
                <span className="text-sm text-muted-foreground">Basis: {line.qty} (piece count)</span>
              ) : (
                <Controller
                  name={`basisValues.${line.id}`}
                  control={control}
                  render={({ field }) => <FormField {...field} type="number" step="0.0001" label="Basis figure" />}
                />
              )}
              <span className="text-sm text-muted-foreground">
                Allocated: {allocationPreview[line.id] ? formatPKR(allocationPreview[line.id].allocatedCostPkr) : '—'}
              </span>
              <span className="text-sm text-muted-foreground">
                Landed/unit: {allocationPreview[line.id] ? formatPKR(allocationPreview[line.id].landedCostPkr) : '—'}
              </span>
            </div>
          ))}
          {missingBasisValues && (
            <p className="text-sm text-destructive">
              Enter a positive basis figure for every attached line before submitting.
            </p>
          )}
        </div>
      )}

      <Button
        type="submit"
        size="lg"
        disabled={isSubmitting || selectedLines.length === 0 || missingBasisValues}
        className="self-end"
      >
        {isSubmitting ? 'Saving…' : 'Create shipment'}
      </Button>
    </form>
  );
}
