import React from 'react';
// Mantine global styles (required for component styling)
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { AppProvider } from './context/AppProvider';
import { AppThemeProvider } from './theme';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Notifications } from '@mantine/notifications';

const el = document.getElementById('root');
if (el) {
  const root = createRoot(el);
  root.render(
    <React.StrictMode>
      <AppThemeProvider>
        <ErrorBoundary>
          <AppProvider>
            <Notifications position="top-right" />
            <App />
          </AppProvider>
        </ErrorBoundary>
      </AppThemeProvider>
    </React.StrictMode>
  );
}
