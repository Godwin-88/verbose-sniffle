import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Session } from '@supabase/supabase-js';

interface AuthState {
  // Flask API key (authorises calls to backend)
  apiKey: string | null;
  userId: string | null;
  // Supabase session (used to identify the user and refresh tokens)
  session: Session | null;

  setAuth: (apiKey: string, userId: string) => void;
  setSession: (session: Session | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: null,
      userId: null,
      session: null,
      setAuth: (apiKey, userId) => set({ apiKey, userId }),
      setSession: (session) => set({ session }),
      logout: () => set({ apiKey: null, userId: null, session: null }),
    }),
    {
      name: 'jh-auth-storage',
      // Don't persist the full session object — Supabase manages its own storage
      partialize: (state) => ({ apiKey: state.apiKey, userId: state.userId }),
    }
  )
);
