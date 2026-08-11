import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthRouteProtection } from '@/components/common/AuthRouteProtection';
import { ProtectedRoute } from '@/components/common/ProtectedRoute';
import { SignInPage } from '@/pages/AuthPages/SignInPage';
import { SignUpPage } from '@/pages/AuthPages/SignUpPage';
import { ForgotPasswordPage } from '@/pages/AuthPages/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/AuthPages/ResetPasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { CatalogPage } from '@/pages/CatalogPage';
import { PartiesPage } from '@/pages/PartiesPage';
import { PurchaseOrdersPage } from '@/pages/PurchaseOrdersPage';
import { PurchaseOrderCreatePage } from '@/pages/PurchaseOrderCreatePage';
import { PurchaseOrderDetailPage } from '@/pages/PurchaseOrderDetailPage';
import { CargoShipmentsPage } from '@/pages/CargoShipmentsPage';
import { CargoShipmentCreatePage } from '@/pages/CargoShipmentCreatePage';
import { CargoShipmentDetailPage } from '@/pages/CargoShipmentDetailPage';
import { InventoryPage } from '@/pages/InventoryPage';
import { SalesOrdersPage } from '@/pages/SalesOrdersPage';
import { SalesOrderCreatePage } from '@/pages/SalesOrderCreatePage';
import { SalesOrderDetailPage } from '@/pages/SalesOrderDetailPage';
import { PaymentsPage } from '@/pages/PaymentsPage';
import { ExpensesPage } from '@/pages/ExpensesPage';
import { PartyDetailPage } from '@/pages/PartyDetailPage';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/common/Sidebar';
import { BottomNav } from '@/components/common/BottomNav';
import { Footer } from '@/components/Footer';
import { TooltipProvider } from '@/components/ui/tooltip';

export function App() {
  return (
    <TooltipProvider>
      <div className="flex min-h-svh">
        <Sidebar />
        <div className="flex min-h-svh min-w-0 flex-1 flex-col pb-16 md:pb-0">
          <Navbar />
          <main className="min-w-0 flex-1 bg-muted/30">
            <Routes>
              <Route element={<AuthRouteProtection />}>
                <Route path="/sign-in" element={<SignInPage />} />
                <Route path="/sign-up" element={<SignUpPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />
              </Route>

              <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/catalog" element={<CatalogPage />} />
                <Route path="/parties" element={<PartiesPage />} />
                <Route path="/parties/:partyId" element={<PartyDetailPage />} />
                <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
                <Route path="/purchase-orders/new" element={<PurchaseOrderCreatePage />} />
                <Route path="/purchase-orders/:orderId" element={<PurchaseOrderDetailPage />} />
                <Route path="/cargo-shipments" element={<CargoShipmentsPage />} />
                <Route path="/cargo-shipments/new" element={<CargoShipmentCreatePage />} />
                <Route path="/cargo-shipments/:shipmentId" element={<CargoShipmentDetailPage />} />
                <Route path="/inventory" element={<InventoryPage />} />
                <Route path="/sales-orders" element={<SalesOrdersPage />} />
                <Route path="/sales-orders/new" element={<SalesOrderCreatePage />} />
                <Route path="/sales-orders/:orderId" element={<SalesOrderDetailPage />} />
                <Route path="/payments" element={<PaymentsPage />} />
                <Route path="/expenses" element={<ExpensesPage />} />
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
              </Route>

              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </main>
          <Footer />
        </div>
        <BottomNav />
      </div>
    </TooltipProvider>
  );
}
