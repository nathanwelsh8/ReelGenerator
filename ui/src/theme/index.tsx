import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { ReactNode } from 'react';
import { theme } from './theme';

export const AppThemeProvider = ({ children }: { children: ReactNode }) => (
  <MantineProvider theme={theme} defaultColorScheme="dark">
    <Notifications position="top-right" />
    {children}
  </MantineProvider>
);
