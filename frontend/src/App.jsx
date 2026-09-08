import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/layout/ProtectedRoute';
import { DataProvider } from './context/DataContext';

import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import AcceptInvitePage from './pages/auth/AcceptInvitePage';
import DashboardPage from './pages/DashboardPage';
import AddTransactionPage from './pages/AddTransactionPage';
import TransactionsPage from './pages/TransactionsPage';
import AccountsPage from './pages/AccountsPage';
import IncomePage from './pages/IncomePage';
import BudgetsPage from './pages/BudgetsPage';
import GoalsPage from './pages/GoalsPage';
import PortfolioPage from './pages/PortfolioPage';
import RewardsPage from './pages/RewardsPage';
import FamilyPage from './pages/FamilyPage';
import ProfilePage from './pages/ProfilePage';
import SettingsPage from './pages/SettingsPage';
import ToolsLayout from './pages/tools/ToolsLayout';
import ToolsIndex from './pages/tools/ToolsIndex';
import HomeLoanCalculator from './pages/tools/HomeLoanCalculator';
import FDCalculator from './pages/tools/FDCalculator';
import RDCalculator from './pages/tools/RDCalculator';
import SIPCalculator from './pages/tools/SIPCalculator';
import IncomeTaxCalculator from './pages/tools/IncomeTaxCalculator';

// The authenticated area shares one DataProvider so a page switch doesn't
// refetch everything — AppLayout renders the routed page via <Outlet/>.
function AuthedApp() {
  return (
    <DataProvider>
      <AppLayout />
    </DataProvider>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/invite/:token" element={<AcceptInvitePage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AuthedApp />}>
          <Route index element={<DashboardPage />} />
          <Route path="add" element={<AddTransactionPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="accounts" element={<AccountsPage />} />
          <Route path="income" element={<IncomePage />} />
          <Route path="budgets" element={<BudgetsPage />} />
          <Route path="goals" element={<GoalsPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="rewards" element={<RewardsPage />} />
          <Route path="tools" element={<ToolsLayout />}>
            <Route index element={<ToolsIndex />} />
            <Route path="home-loan" element={<HomeLoanCalculator />} />
            <Route path="fd" element={<FDCalculator />} />
            <Route path="rd" element={<RDCalculator />} />
            <Route path="sip" element={<SIPCalculator />} />
            <Route path="tax" element={<IncomeTaxCalculator />} />
          </Route>
          <Route path="family" element={<FamilyPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
