import { Wallet } from 'lucide-react';
import { CrudTable } from '@/components/common/CrudTable';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { paymentAccountCrudConfig } from '@/components/payments/PaymentAccountCrudConfig';
import { usePaymentAccountBalances, usePaymentMethods } from '@/hooks/paymentsHooks/paymentsQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

export function PaymentAccountList() {
  const { data: balancesData } = usePaymentAccountBalances();
  const { data: methodsData } = usePaymentMethods(LOOKUP_PAGE);

  const balanceById = Object.fromEntries((balancesData ?? []).map((b) => [b.id, b.balance]));
  const methodNameById = Object.fromEntries((methodsData?.items ?? []).map((m) => [m.id, m.name]));
  const methodOptions = (methodsData?.items ?? []).map((m) => ({ value: String(m.id), label: m.name }));

  // Balance isn't a column on PaymentAccountRead — joined in here from a second
  // query by id, the same shape SalesOrderList.jsx uses for customer names.
  // payment_method_id's display value and its drawer field options are both
  // injected here too, since the static config can't fetch a hook.
  const config = {
    ...paymentAccountCrudConfig,
    columns: [
      ...paymentAccountCrudConfig.columns.map((column) =>
        column.key === 'payment_method_id'
          ? { ...column, render: (row) => methodNameById[row.payment_method_id] ?? `Method #${row.payment_method_id}` }
          : column,
      ),
      {
        key: 'balance',
        label: 'Balance',
        render: (row) => (
          <CurrencyAmount value={balanceById[row.id] ?? row.opening_balance} className="font-medium" />
        ),
      },
    ],
    fields: paymentAccountCrudConfig.fields.map((field) =>
      field.name === 'payment_method_id' ? { ...field, options: methodOptions } : field,
    ),
  };

  return (
    <CrudTable
      config={config}
      title="Payment Accounts"
      description="Concrete accounts under each payment method — balance is the sum of every ledger entry posted against it."
      icon={Wallet}
      addLabel="Add account"
      entityLabel="payment account"
    />
  );
}
