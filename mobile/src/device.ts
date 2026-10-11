import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
const KEY = 'meridian-phone-device';

export async function loadDevice(): Promise<string | null> {
  if (Platform.OS === 'web') return localStorage.getItem(KEY);
  return SecureStore.getItemAsync(KEY);
}
export async function saveDevice(token: string | null) {
  if (Platform.OS === 'web') {
    if (token) localStorage.setItem(KEY, token); else localStorage.removeItem(KEY);
  } else if (token) await SecureStore.setItemAsync(KEY, token);
  else await SecureStore.deleteItemAsync(KEY);
}
