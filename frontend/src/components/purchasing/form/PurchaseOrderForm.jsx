import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect } from '@/components/custom';
import { purchaseOrderCreateSchema } from '@/validations/purchasingSchemas';
import { useCreatePurchaseOrder } from '@/hooks/purchasingHooks/purchasingMutations';
import { useExchangeRateForDate } from '@/hooks/purchasingHooks/purchasingQueries';
import { useChinaVendorParties, useLocalVendorParties } from '@/hooks/partyHooks/partyQueries';
import { useItems } from '@/hooks/catalogHooks/itemQueries';
import { toMoney, computeRmbAmount, computePkrAmount, computeSaleAmount, formatRMB, formatPKR } from '@/utils/currencyUtils';
import { PURCHASE_ORDER_SOURCE, PURCHASE_ORDER_SOURCE_OPTIONS } from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 100 };
const EMPTY_LINE = { item_id: '', qty: '', rate_rmb: '', rate_pkr: '' };
const todayIso = () => new Date().toISOString().slice(0, 10);

export function PurchaseOrderForm({ onSuccess }) {
  const { vendors: chinaVendors } = useChinaVendorParties();
  const { vendors: localVendors } = useLocalVendorParties();
  const { data: itemsData } = useItems(LOOKUP_PAGE);

  const itemOptions = (itemsData?.items ?? []).map((item) => ({
    value: String(item.id),
    label: item.sku,
  }));

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(purchaseOrderCreateSchema, {}, { raw: true }),
    defaultValues: { party_id: '', order_date: todayIso(), source: PURCHASE_ORDER_SOURCE.CHINA, lines: [EMPTY_LINE] },
  });
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'lines' });
  const createMutation = useCreatePurchaseOrder();

  const source = watch('source');
  const isChina = source === PURCHASE_ORDER_SOURCE.CHINA;
  const orderDate = watch('order_date');
  const lines = watch('lines') ?? [];
  // Always called (Rules of Hooks) — only used to gate submit / render the warning
  // when isChina is true. A local order never needs this lookup.
  const { rate: exchangeRate, isLoading: isRateLoading } = useExchangeRateForDate(orderDate);

  const vendorOptions = (isChina ? chinaVendors : localVendors).map((v) => ({ value: String(v.id), label: v.name }));

  // Pair each rendered field with its live watched values defensively, so a
  // remove() mid-edit can't transiently mis-pair a row with another row's numbers.
  const rows = fields.map((field, index) => ({ ...field, ...(lines[index] ?? {}) }));

  const rawTotals = rows.reduce(
    (acc, row) => ({
      rmb: acc.rmb + (isChina ? computeRmbAmount(row.qty, row.rate_rmb) : 0),
      pkr: acc.pkr + (isChina
        ? (exchangeRate ? computePkrAmount(row.qty, row.rate_rmb, exchangeRate.rate) : 0)
        : computeSaleAmount(row.qty, row.rate_pkr)),
    }),
    { rmb: 0, pkr: 0 },
  );
  const totals = { rmb: toMoney(rawTotals.rmb), pkr: toMoney(rawTotals.pkr) };

  // Switching source invalidates the previously selected vendor and any entered
  // rates — a china-role vendor and an RMB rate mean nothing once switched to
  // local, and vice versa.
  const handleSourceChange = (field, value) => {
    field.onChange(value);
    setValue('party_id', '');
    replace([EMPTY_LINE]);
  };

  const onSubmit = async (values) => {
    try {
      const created = await createMutation.mutateAsync({
        party_id: values.party_id,
        order_date: values.order_date,
        source: values.source,
        lines: values.lines.map(({ item_id, qty, rate_rmb, rate_pkr }) =>
          values.source === PURCHASE_ORDER_SOURCE.CHINA
            ? { item_id, qty, rate_rmb }
            : { item_id, qty, rate_pkr },
        ),
      });
      onSuccess?.(created);
    } catch {
      // fetchClient already toasted the backend's error detail (role mismatch,
      // missing exchange rate, dead item id) — keep the form open to fix and retry.
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Controller
          name="source"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label="Source"
              options={PURCHASE_ORDER_SOURCE_OPTIONS}
              onChange={(value) => handleSourceChange(field, value)}
              error={errors.source?.message}
            />
          )}
        />
        <Controller
          name="party_id"
          control={control}
          render={({ field }) => (
            <FormSelect
              {...field}
              label={isChina ? 'Vendor (china vendor)' : 'Vendor (local vendor)'}
              placeholder="Select a vendor"
              options={vendorOptions}
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

      {isChina && !isRateLoading && !exchangeRate && (
        <p className="text-sm text-destructive">
          No exchange rate is set for {orderDate}. Add one in Settings → Exchange Rates before submitting.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {rows.map((row, index) => (
          <div key={row.id} className="grid gap-3 rounded-lg border p-3 md:grid-cols-[2fr_1fr_1fr_auto_auto] md:items-start">
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
            <Controller
              name={`lines.${index}.qty`}
              control={control}
              render={({ field }) => (
                <FormField {...field} type="number" step="0.01" label="Qty" error={errors.lines?.[index]?.qty?.message} />
              )}
            />
            {isChina ? (
              <Controller
                name={`lines.${index}.rate_rmb`}
                control={control}
                render={({ field }) => (
                  <FormField
                    {...field}
                    type="number"
                    step="0.01"
                    label="Rate (RMB)"
                    error={errors.lines?.[index]?.rate_rmb?.message}
                  />
                )}
              />
            ) : (
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
            )}
            <div className="flex flex-col justify-end gap-0.5 text-sm text-muted-foreground">
              {isChina ? (
                <>
                  <span>{formatRMB(computeRmbAmount(row.qty, row.rate_rmb))}</span>
                  {exchangeRate && <span>{formatPKR(computePkrAmount(row.qty, row.rate_rmb, exchangeRate.rate))}</span>}
                </>
              ) : (
                <span>{formatPKR(computeSaleAmount(row.qty, row.rate_pkr))}</span>
              )}
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

      <div className="flex justify-end gap-6 border-t pt-4 text-sm">
        {isChina && (
          <span>
            Total RMB: <strong>{formatRMB(totals.rmb)}</strong>
          </span>
        )}
        <span>
          Total PKR: <strong>{formatPKR(totals.pkr)}</strong>
        </span>
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting || (isChina && !exchangeRate)} className="self-end">
        {isSubmitting ? 'Saving…' : 'Create purchase order'}
      </Button>
    </form>
  );
}
