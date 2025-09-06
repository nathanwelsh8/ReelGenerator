import React, { useEffect, useRef } from 'react';
import { Container, Title, Card, Stack, Text, Loader } from '@mantine/core';
import { useAuth } from '../context/useAuth';
import { useNavigate } from 'react-router-dom';

type GoogleAccounts = {
  id: {
    initialize: (opts: { client_id: string; callback: (resp: { credential: string }) => void }) => void;
    renderButton: (el: HTMLElement, opts: { theme: string; size: string }) => void;
  }
};
declare global { interface Window { google?: { accounts: GoogleAccounts } } }

export const Login: React.FC = () => {
  const { user, loading, loginWithIdToken } = useAuth();
  const nav = useNavigate();
  const btnRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { if (user && !loading) nav('/'); }, [user, loading, nav]);

  useEffect(() => {
    if (!window.google || !btnRef.current) return;
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
    if (!clientId) {
      console.error('VITE_GOOGLE_CLIENT_ID missing. Set it in UI env (.env or launch config).');
      return;
    }
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (resp: { credential: string }) => {
        if (resp.credential) loginWithIdToken(resp.credential);
      }
    });
    window.google.accounts.id.renderButton(btnRef.current, { theme: 'outline', size: 'large' });
  }, [loginWithIdToken]);

  return (
    <Container size="xs" py="xl">
      <Card withBorder radius="md" shadow="sm">
        <Stack gap="md">
          <Title order={3}>Sign in</Title>
          <Text c="dimmed" size="sm">Use your Google account to continue.</Text>
          {loading && !user && <Loader />}
          <div ref={btnRef} style={{ display: user ? 'none' : 'block' }} />
        </Stack>
      </Card>
    </Container>
  );
};
