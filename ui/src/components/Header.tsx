import { NavLink, useNavigate } from 'react-router-dom';
import { Group, Container, Title, Anchor, Avatar, Menu, Text, Button, UnstyledButton } from '@mantine/core';
import { useAuth } from '../context/useAuth';

export const Header = () => {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const doLogout = async () => { await logout(); nav('/login'); };
  return (
    <Container fluid px="md" py={8} style={{ borderBottom: '1px solid var(--mantine-color-dark-6)' }}>
      <Group justify="space-between" wrap="nowrap">
        <Title order={4} style={{ letterSpacing: '.5px' }}>Brainrot Factory</Title>
        <Group gap="sm" wrap="nowrap">
          {user && (
            <>
              <Anchor component={NavLink} to="/" end fw={500} style={{ textDecoration: 'none' }}>Projects</Anchor>
              <Anchor component={NavLink} to="/characters" fw={500} style={{ textDecoration: 'none' }}>Characters</Anchor>
              <Menu shadow="md" width={220} position="bottom-end" withinPortal>
                <Menu.Target>
                  <UnstyledButton style={{ display: 'flex', alignItems: 'center' }} aria-label="User menu">
                    <Avatar
                      src={user.picture}
                      alt={user.name || user.email || 'User'}
                      radius="xl"
                      size={32}
                      color="blue"
                    >
                      {(!user.picture && (user.name || user.email)) ? (user.name || user.email || '?')[0].toUpperCase() : null}
                    </Avatar>
                  </UnstyledButton>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>
                    <Text size="sm" fw={500} truncate>{user.name || user.email || 'Signed in'}</Text>
                  </Menu.Label>
                  <Menu.Divider />
                  <Menu.Item>
                    <Button fullWidth size="xs" variant="light" color="red" onClick={doLogout}>Logout</Button>
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </>
          )}
        </Group>
      </Group>
    </Container>
  );
};
