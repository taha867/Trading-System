import { useSearchParams } from 'react-router-dom';
import { Tag, Smartphone, Package } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { CrudTable } from '@/components/common/CrudTable';
import { categoryCrudConfig } from '@/components/catalog/CategoryCrudConfig';
import { modelCrudConfig } from '@/components/catalog/ModelCrudConfig';
import { useItemCrudConfig } from '@/components/catalog/ItemCrudConfig';

const DEFAULT_TAB = 'categories';

function ItemsTab() {
  const config = useItemCrudConfig();
  return (
    <CrudTable
      config={config}
      title="Items"
      description="Category + model + variant = one SKU — what a purchase order line actually points at."
      icon={Package}
      addLabel="Add item"
      entityLabel="item"
    />
  );
}

export function CatalogContainer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || DEFAULT_TAB;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Catalog</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Categories, models, and items — what you buy and sell, nothing hard-coded.
        </p>
      </div>

      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <TabsList>
          <TabsTrigger value="categories">
            <Tag className="size-4" />
            Categories
          </TabsTrigger>
          <TabsTrigger value="models">
            <Smartphone className="size-4" />
            Models
          </TabsTrigger>
          <TabsTrigger value="items">
            <Package className="size-4" />
            Items
          </TabsTrigger>
        </TabsList>
        <TabsContent value="categories" className="pt-4">
          <CrudTable
            config={categoryCrudConfig}
            title="Categories"
            description="Cover, Protector, Charger — the product families items are classified into."
            icon={Tag}
            addLabel="Add category"
            entityLabel="category"
          />
        </TabsContent>
        <TabsContent value="models" className="pt-4">
          <CrudTable
            config={modelCrudConfig}
            title="Models"
            description="iPhone 13, Galaxy A54 — priority is set here and drives Phase 8's reorder ranking."
            icon={Smartphone}
            addLabel="Add model"
            entityLabel="model"
          />
        </TabsContent>
        <TabsContent value="items" className="pt-4">
          <ItemsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
