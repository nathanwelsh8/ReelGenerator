import React, { createContext, useContext, useState, ReactNode } from 'react';

interface UIContextValue {
  loading: boolean;
  setLoading: (v: boolean) => void;
}

const UIContext = createContext<UIContextValue | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [loading, setLoading] = useState(false);
  return (
    <UIContext.Provider value={{ loading, setLoading }}>
      {children}
    </UIContext.Provider>
  );
};

export const useUI = () => {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error('useUI must be inside AppProvider');
  return ctx;
};
