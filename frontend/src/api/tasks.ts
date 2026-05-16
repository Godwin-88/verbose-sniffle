import { apiClient } from './client';

export const getTasks = async () => {
  const { data } = await apiClient.get('/tasks');
  return data;
};

export const getTask = async (id: string) => {
  const { data } = await apiClient.get(`/tasks/${id}`);
  return data;
};
