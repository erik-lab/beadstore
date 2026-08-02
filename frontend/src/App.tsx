import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { ProtectedRoute } from "./app/ProtectedRoute";
import { Layout } from "./app/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { ProductsListPage } from "./pages/products/ProductsListPage";
import { ProductFormPage } from "./pages/products/ProductFormPage";
import { ProductDetailPage } from "./pages/products/ProductDetailPage";
import { CatalogListingsListPage } from "./pages/catalogListings/CatalogListingsListPage";
import { CatalogListingFormPage } from "./pages/catalogListings/CatalogListingFormPage";
import { CatalogListingDetailPage } from "./pages/catalogListings/CatalogListingDetailPage";
import { InventoryUnitsListPage } from "./pages/inventoryUnits/InventoryUnitsListPage";
import { InventoryUnitFormPage } from "./pages/inventoryUnits/InventoryUnitFormPage";
import { InventoryUnitDetailPage } from "./pages/inventoryUnits/InventoryUnitDetailPage";
import { VendorsListPage } from "./pages/vendors/VendorsListPage";
import { VendorFormPage } from "./pages/vendors/VendorFormPage";
import { VendorDetailPage } from "./pages/vendors/VendorDetailPage";
import { LocationsListPage } from "./pages/locations/LocationsListPage";
import { LocationFormPage } from "./pages/locations/LocationFormPage";
import { PurchaseOrdersListPage } from "./pages/purchaseOrders/PurchaseOrdersListPage";
import { PurchaseOrderFormPage } from "./pages/purchaseOrders/PurchaseOrderFormPage";
import { PurchaseOrderDetailPage } from "./pages/purchaseOrders/PurchaseOrderDetailPage";
import { ReceivePage } from "./pages/receiving/ReceivePage";
import { QuickReceivePage } from "./pages/receiving/QuickReceivePage";
import { OpenOrdersPage } from "./pages/operations/OpenOrdersPage";
import { InventoryOnHandPage } from "./pages/operations/InventoryOnHandPage";
import { UnresolvedItemsPage } from "./pages/operations/UnresolvedItemsPage";
import { DiscrepanciesPage } from "./pages/operations/DiscrepanciesPage";
import { OrderEmailScanPage } from "./pages/OrderEmailScanPage";
import { UtilitiesPage } from "./pages/utilities/UtilitiesPage";
import { HintsMaintenancePage } from "./pages/utilities/HintsMaintenancePage";
import { CategoryMaintenancePage } from "./pages/utilities/CategoryMaintenancePage";

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />

          <Route path="products" element={<ProductsListPage />} />
          <Route path="products/new" element={<ProductFormPage />} />
          <Route path="products/:id" element={<ProductDetailPage />} />
          <Route path="products/:id/edit" element={<ProductFormPage />} />

          <Route path="catalog-listings" element={<CatalogListingsListPage />} />
          <Route path="catalog-listings/new" element={<CatalogListingFormPage />} />
          <Route path="catalog-listings/:id" element={<CatalogListingDetailPage />} />
          <Route path="catalog-listings/:id/edit" element={<CatalogListingFormPage />} />

          <Route path="inventory" element={<InventoryUnitsListPage />} />
          <Route path="inventory/new" element={<InventoryUnitFormPage />} />
          <Route path="inventory/:id" element={<InventoryUnitDetailPage />} />
          <Route path="inventory/:id/edit" element={<InventoryUnitFormPage />} />

          <Route path="vendors" element={<VendorsListPage />} />
          <Route path="vendors/new" element={<VendorFormPage />} />
          <Route path="vendors/:id" element={<VendorDetailPage />} />
          <Route path="vendors/:id/edit" element={<VendorFormPage />} />

          <Route path="locations" element={<LocationsListPage />} />
          <Route path="locations/new" element={<LocationFormPage />} />
          <Route path="locations/:id/edit" element={<LocationFormPage />} />

          <Route path="purchase-orders" element={<PurchaseOrdersListPage />} />
          <Route path="purchase-orders/new" element={<PurchaseOrderFormPage />} />
          <Route path="purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
          <Route path="purchase-orders/:id/receive" element={<ReceivePage />} />

          <Route path="receiving/quick-receive" element={<QuickReceivePage />} />

          <Route path="order-email-scan" element={<OrderEmailScanPage />} />

          <Route path="operations/open-orders" element={<OpenOrdersPage />} />
          <Route path="operations/inventory-on-hand" element={<InventoryOnHandPage />} />
          <Route path="operations/unresolved-items" element={<UnresolvedItemsPage />} />
          <Route path="operations/receiving-discrepancies" element={<DiscrepanciesPage />} />

          <Route path="utilities" element={<UtilitiesPage />} />
          <Route path="utilities/hints" element={<HintsMaintenancePage />} />
          <Route path="utilities/categories" element={<CategoryMaintenancePage />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
