import { apiClient } from './client';

export const setupProfile = async (payload: {
  email: string;
  profile?: any;
  api_key?: string;
}) => {
  const { data } = await apiClient.post('/profile/setup', payload);
  return data;
};

export const getProfile = async () => {
  const { data } = await apiClient.get('/profile');
  return data;
};

export const updateProfile = async (profile: any) => {
  const { data } = await apiClient.put('/profile', { profile });
  return data;
};
