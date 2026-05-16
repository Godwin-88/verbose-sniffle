import axios from 'axios';

// AUTH DISABLED FOR FEATURE TESTING — re-enable Zustand import when auth bug is fixed
// import { useAuthStore } from '@/store/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5055';

// DEV: use master key from env directly
const API_KEY = import.meta.env.VITE_API_KEY;

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
