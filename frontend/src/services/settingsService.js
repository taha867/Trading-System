import { fetchClient } from '@/middleware/fetchClient';

export async function getSetting() {
  const { data } = await fetchClient.get('/settings');
  return data; // SettingRead
}

export async function updateSetting(payload) {
  const { data } = await fetchClient.put('/settings', payload);
  return data; // SettingRead
}
