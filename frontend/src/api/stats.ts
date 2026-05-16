import { apiClient } from './client';

export const getStats = async () => {
  const { data } = await apiClient.get('/stats');
  return data;
};

export const getHealth = async () => {
  const { data } = await apiClient.get('/health');
  return data;
};

export const getUpcomingReminders = async (params?: { deadline_days?: number; stale_hours?: number }) => {
  const { data } = await apiClient.get('/reminders/upcoming', { params });
  return data;
};

export const sendReminderDigest = async (payload?: { deadline_days?: number; stale_hours?: number }) => {
  const { data } = await apiClient.post('/reminders/send-digest', payload || {});
  return data;
};
