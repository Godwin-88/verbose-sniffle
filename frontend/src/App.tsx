import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';

// AUTH DISABLED FOR FEATURE TESTING — re-enable when auth bug is fixed
// import { useEffect } from 'react';
// import { useAuthStore } from './store/auth';
// import { supabase } from './lib/supabase';
// import Setup from './pages/Setup';
// import AuthCallback from './pages/AuthCallback';

// Pages
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Scholarships from './pages/Scholarships';
import Tasks from './pages/Tasks';
import Profile from './pages/Profile';
import Settings from './pages/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// AUTH DISABLED — ProtectedRoute commented out
// function ProtectedRoute({ children }: { children: React.ReactNode }) {
//   const { apiKey } = useAuthStore();
//   if (!apiKey) return <Navigate to="/setup" replace />;
//   return <>{children}</>;
// }

// AUTH DISABLED — Supabase session sync commented out
// function AuthSync() {
//   const { logout } = useAuthStore();
//   useEffect(() => {
//     const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
//       if (event === 'SIGNED_OUT') logout();
//     });
//     return () => subscription.unsubscribe();
//   }, [logout]);
//   return null;
// }

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* <AuthSync /> */}
        <Routes>
          {/* <Route path="/setup" element={<Setup />} /> */}
          {/* <Route path="/auth/callback" element={<AuthCallback />} /> */}
          <Route path="/" element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="scholarships" element={<Scholarships />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="profile" element={<Profile />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
