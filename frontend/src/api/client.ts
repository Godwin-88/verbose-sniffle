import axios from 'axios';

// AUTH DISABLED FOR FEATURE TESTING — re-enable Zustand import when auth bug is fixed
// import { useAuthStore } from '@/store/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5055';

// DEV: hardcoded master key — matches API_KEY in root .env
// TODO: restore env var / auth when fixing login bug
const API_KEY = 'e3fdc5aa427ae1b3a07d831248338ff37593e6a62f1e91111420503035196b5b';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  // AUTH DISABLED: use env key directly
  // const key = useAuthStore.getState().apiKey;
  if (API_KEY) config.headers['X-API-Key'] = API_KEY;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // AUTH DISABLED: logout/redirect on 401 commented out
    // if (error.response?.status === 401 || error.response?.status === 403) {
    //   useAuthStore.getState().logout();
    //   if (window.location.pathname !== '/setup') {
    //     window.location.href = '/setup';
    //   }
    // }
    return Promise.reject(error);
  }
);
