import { api } from './apiClient';

export interface User { id:number; email?:string; name?:string; picture?:string }

export async function loginWithGoogleIdToken(idToken: string): Promise<User> {
  const res = await api.post('/auth/google', { id_token: idToken });
  return res.data;
}

export async function fetchMe(): Promise<User | null> {
  try { const res = await api.get('/auth/me'); return res.data; } catch { return null; }
}

export async function logout(): Promise<void> {
  try { await api.post('/auth/logout'); } catch {/* ignore */}
}
