import React, { createContext, useEffect, useState, useCallback } from 'react';
import { fetchMe, loginWithGoogleIdToken, logout, type User } from '../services/authService';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  loginWithIdToken: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContextInternal = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    const me = await fetchMe();
    setUser(me);
    setLoading(false);
  }, []);

  useEffect(()=>{ bootstrap(); }, [bootstrap]);

  const loginWithIdToken = async (token: string) => {
    setLoading(true);
    try { const u = await loginWithGoogleIdToken(token); setUser(u); }
    finally { setLoading(false); }
  };
  const doLogout = async () => { await logout(); setUser(null); };

  return <AuthContextInternal.Provider value={{ user, loading, loginWithIdToken, logout: doLogout }}>{children}</AuthContextInternal.Provider>;
};
