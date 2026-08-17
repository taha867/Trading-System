import { useSearchParams } from 'react-router-dom';
import { ArrowLeftRight, Wallet, Truck, Scale, Tags, Store } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { CrudTable } from '@/components/common/CrudTable';
import { exchangeRateCrudConfig } from '@/components/purchasing/ExchangeRateCrudConfig';
import { paymentMethodCrudConfig } from '@/components/payments/PaymentMethodCrudConfig';
import { cargoModeCrudConfig } from '@/components/cargo/CargoModeCrudConfig';
import { cargoCostBasisCrudConfig } from '@/components/cargo/CargoCostBasisCrudConfig';
import { expenseCategoryCrudConfig } from '@/components/expenses/ExpenseCategoryCrudConfig';
import { ShopSettingsForm } from '@/components/settings/ShopSettingsForm';

const DEFAULT_TAB = 'exchange-rates';

export function SettingsContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || DEFAULT_TAB;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The lookup tables every other screen in this app is built on — add or edit them here, nothing is
          hard-coded.
        </p>
      </div>

      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="exchange-rates">
              <ArrowLeftRight className="size-4" />
              Exchange Rates
            </TabsTrigger>
            <TabsTrigger value="payment-methods">
              <Wallet className="size-4" />
              Payment Methods
            </TabsTrigger>
            <TabsTrigger value="cargo-modes">
              <Truck className="size-4" />
              Cargo Modes
            </TabsTrigger>
            <TabsTrigger value="cargo-cost-bases">
              <Scale className="size-4" />
              Cost Bases
            </TabsTrigger>
            <TabsTrigger value="expense-categories">
              <Tags className="size-4" />
              Expense Categories
            </TabsTrigger>
            <TabsTrigger value="shop">
              <Store className="size-4" />
              Shop
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="exchange-rates" className="pt-4">
          <CrudTable
            config={exchangeRateCrudConfig}
            title="Exchange Rates"
            description="Today's RMB → PKR rate, snapshotted onto every purchase order line at creation time."
            icon={ArrowLeftRight}
            addLabel="Add rate"
            entityLabel="exchange rate"
          />
        </TabsContent>
        <TabsContent value="payment-methods" className="pt-4">
          <CrudTable
            config={paymentMethodCrudConfig}
            title="Payment Methods"
            description="The payment rails available whenever a transaction gets recorded."
            icon={Wallet}
            addLabel="Add method"
            entityLabel="payment method"
          />
        </TabsContent>
        <TabsContent value="cargo-modes" className="pt-4">
          <CrudTable
            config={cargoModeCrudConfig}
            title="Cargo Modes"
            description="Sea, Air — how a shipment travels."
            icon={Truck}
            addLabel="Add mode"
            entityLabel="cargo mode"
          />
        </TabsContent>
        <TabsContent value="cargo-cost-bases" className="pt-4">
          <CrudTable
            config={cargoCostBasisCrudConfig}
            title="Cargo Cost Bases"
            description="How a shipment's freight cost splits across its lines — Weight, CBM, or Piece."
            icon={Scale}
            addLabel="Add cost basis"
            entityLabel="cost basis"
          />
        </TabsContent>
        <TabsContent value="expense-categories" className="pt-4">
          <CrudTable
            config={expenseCategoryCrudConfig}
            title="Expense Categories"
            description="Food, repairs, rent, bills, salaries — daily float vs. monthly fixed overhead."
            icon={Tags}
            addLabel="Add category"
            entityLabel="expense category"
          />
        </TabsContent>
        <TabsContent value="shop" className="pt-4">
          <ShopSettingsForm />
        </TabsContent>
      </Tabs>
    </div>
  );
}
