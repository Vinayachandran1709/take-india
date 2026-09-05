import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from './components/ProtectedRoute'
import { Shell } from './components/Shell'
import { AuthPage } from './pages/AuthPage'
import { OverviewPage } from './pages/OverviewPage'
import { SchedulesPage } from './pages/SchedulesPage'
import { ServicesPage } from './pages/ServicesPage'
import { SettingsPage } from './pages/SettingsPage'

function DashboardLayout() {
  return <ProtectedRoute><Shell><Outlet /></Shell></ProtectedRoute>
}

export default function App() {
  return <Routes><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/signup" element={<AuthPage mode="signup" />} /><Route path="/dashboard" element={<DashboardLayout />}><Route index element={<OverviewPage />} /><Route path="services" element={<ServicesPage />} /><Route path="settings" element={<SettingsPage />} /><Route path="schedules" element={<SchedulesPage />} /></Route><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes>
}
