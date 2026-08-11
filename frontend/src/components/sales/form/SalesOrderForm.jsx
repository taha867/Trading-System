import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { salesOrderCreateSchema } from '@/validations/salesSchemas';
import { useCreateSalesOrder } from '@/hooks/salesHooks/salesMutations';
import { useCustomerParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { useStockLots } from '@/hooks/inventoryHooks/inventoryQueries';
import { toMoney, computeSaleAmount, formatPKR } from '@/utils/currencyUtils';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const EMPTY_LINE = { item_id: '', qty: '', rate_pkr: '' };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function SalesOrderForm({ onSuccess }) {
  const { customers } = useCustomerParties();
  const { data: itemsData } = useItems(LOOKUP_PAGE);
  // Informational only — never validated against in Yup (phase-4-frontend spec §2,
  // decision 3): stock is live, shared, external state that can change between
  // typing and submit. The authoritative check is the backend's own InsufficientStock
  // 422, already toasted generically by fetchClient on submit failure.
  const { data: stockLotsData } = useStockLots({ page: 1, page_size: 100 });

  const itemOptions = (itemsData?.items ?? []).map((item) => ({
    value: String(item.id),
    label: item.sku,
  }));
  const customerOptions = customers.map((p) => ({ value: String(p.id), label: p.name }));
  const availableByItemId = (stockLotsData?.items ?? []).reduce((acc, lot) => {
    const key = String(lot.item_id);
    acc[key] = (acc[key] ?? 0) + Number(lot.qty_remaining);
    return acc;
  }, {});

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(salesOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), lines: [EMPTY_LINE] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreateSalesOrder();

  const lines = watch('lines') ?? [];
  const rows = fields.map((field, index) => ({ ...field, ...(lines[index] ?? {}) }));
  const totalPkr = toMoney(rows.reduce((sum, row) => sum + computeSaleAmount(row.qty, row.rate_pkr), 0));

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        party_id: values.party_id,
        order_date: values.order_date,
        lines: values.lines.map(({ item_id, qty, rate_pkr }) => ({ item_id, qty, rate_pkr })),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch,
      // duplicate item, insufficient stock) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Customer"
              placeholder="Select a customer"
              options={customerOptions}
              error={errors.party_id?.message}
            />
          )}
        />
        <Controller
          name="order_date"
          control={control}
          render={({ field }) => (
            <FormField {...field} type="date" label="Order date" error={errors.order_date?.message} />
          )}
        />
      </div>

      <div className="flex flex-col gap-3">
        {rows.map((row, index) => (
          <div key={row.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[2fr_1fr_1fr_1fr_auto] md:items-start">
            <div className="flex flex-col gap-1">
              <Controller
                name={`lines.${index}.item_id`}
                control={control}
                render={({ field }) => (
                  <FormSelect
                    {...field}
                    label="Item"
                    placeholder="Select an item"
                    options={itemOptions}
                    error={errors.lines?.[index]?.item_id?.message}
                  />
                )}
              />
              {row.item_id && (
                <span className="text-xs text-muted-foreground">In stock: {availableByItemId[row.item_id] ?? 0}</span>
              )}
            </div>
            <Controller
              name={`lines.${index}.qty`}
              control={control}
              render={({ field }) => (
                <FormField {...field} type="number" step="0.01" label="Qty" error={errors.lines?.[index]?.qty?.message} />
              )}
            />
            <Controller
              name={`lines.${index}.rate_pkr`}
              control={control}
              render={({ field }) => (
                <FormField
                  {...field}
                  type="number"
                  step="0.01"
                  label="Rate (PKR)"
                  error={errors.lines?.[index]?.rate_pkr?.message}
                />
              )}
            />
            <div className="flex flex-col justify-end text-sm text-muted-foreground">
              <span>{formatPKR(computeSaleAmount(row.qty, row.rate_pkr))}</span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Remove line"
              onClick={() => remove(index)}
              disabled={rows.length === 1}
              className="justify-self-start md:justify-self-auto"
            >
              <Trash2 className="text-destructive" />
            </Button>
          </div>
        ))}
        {/* react-hook-form places a whole-array Yup .test() error under errors.lines.root,
            not errors.lines, whenever the array also has per-index registered fields
            (lines.0.item_id, etc.) — @hookform/resolvers' toNestErrors nests it there
            to avoid colliding with the per-item error shape. */}
        {errors.lines?.root?.message && <p className="text-sm text-destructive">{errors.lines.root.message}</p>}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_LINE)} className="self-start">
          <Plus /> Add line
        </Button>
      </div>

      <div className="flex justify-end border-t pt-4 text-sm">
        <span>
          Total: <strong>{formatPKR(totalPkr)}</strong>
        </span>
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create sales order'}
      </Button>
    </form>
  );
}
