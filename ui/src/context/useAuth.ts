import { useContext } from 'react';
import { AuthContextInternal } from './AuthContext';

export const useAuth = () => {
  const ctx = useContext(AuthContextInternal);
  if (!ctx) throw new Error('AuthProvider missing');
  return ctx;
};
