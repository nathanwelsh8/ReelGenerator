import { useEffect, useState } from 'react';
import type { Character } from '../types';
import { listCharacters, createCharacter, generateFollowAudio } from '../services/charactersService';
import { Container, Title, Card, Table, Text, Group, Button, Loader, Stack, TextInput, Textarea } from '@mantine/core';
import { notifications } from '@mantine/notifications';

export const Characters = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const data = await listCharacters(); setCharacters(data); } finally { setLoading(false); }
  };
  useEffect(()=>{ load(); }, []);

  const requeueFollow = async (c: Character) => { 
    const nid = `follow-${c.id}`;
    notifications.show({ id:nid, loading:true, title:'Generating audio', message:`Generating follow line for ${c.name}...`, autoClose:false, withCloseButton:false });
    try { await generateFollowAudio(c.id); notifications.update({ id:nid, loading:false, title:'Audio generated', message:'Follow line audio ready', color:'green', autoClose:2000 }); load(); }
    catch (e) { notifications.update({ id:nid, loading:false, title:'Generation failed', message: e instanceof Error ? e.message : 'Error', color:'red', autoClose:4000 }); }
  };

  return (
    <Container size="md" py="md">
      <Title order={2} mb="md">Characters</Title>
      <NewCharacterForm onCreated={load} />
      {loading && <Group justify="center" mt="md"><Loader /></Group>}
      {!loading && (
        <Card withBorder radius="md" mt="md">
          <Table striped highlightOnHover withTableBorder withColumnBorders fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Follow Text</Table.Th>
                <Table.Th>Audio</Table.Th>
                <Table.Th>Action</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {characters.map(c => (
                <Table.Tr key={c.id}>
                  <Table.Td>{c.name}</Table.Td>
                  <Table.Td style={{ maxWidth:300 }}>{c.follow_line || <Text c="dimmed" span>—</Text>}</Table.Td>
                  <Table.Td>{c.follow_line_audio ? <audio controls src={c.follow_line_audio} /> : <Text c="dimmed" span>Missing</Text>}</Table.Td>
                  <Table.Td>
                    {!c.follow_line_audio && <Button size="xs" variant="light" onClick={()=>requeueFollow(c)}>Generate Audio</Button>}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}
    </Container>
  );
};

// --- new character form ---
import { useState as useS } from 'react';
import { notifications as n } from '@mantine/notifications';

const NewCharacterForm = ({ onCreated }: { onCreated: () => void }) => {
  const [name, setName] = useS('');
  const [parrotPath, setParrotPath] = useS('');
  const [followText, setFollowText] = useS('');
  const [imageFilename, setImageFilename] = useS('');
  const [submitting, setSubmitting] = useS(false);
  const [error, setError] = useS<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('Name required'); return; }
    setError(null); setSubmitting(true);
    try {
  n.show({ id:'create-character', loading:true, title:'Creating character', message:'Submitting character...', autoClose:false, withCloseButton:false });
  await createCharacter({ name, parrot_ai_path: parrotPath, image_filename: imageFilename, active: true, follow_line: followText });
  n.update({ id:'create-character', loading:false, title:'Character created', message:'Character added', color:'green', autoClose:2000 });
      setName(''); setParrotPath(''); setFollowText(''); setImageFilename('');
      onCreated();
    } catch (e: unknown) {
  const msg = e instanceof Error ? e.message : 'Failed';
  if (e instanceof Error) setError(e.message); else setError('Failed');
  n.update({ id:'create-character', loading:false, title:'Create failed', message: msg, color:'red', autoClose:4000 });
    }
    finally { setSubmitting(false); }
  };

  return (
    <Card withBorder radius="md" mb="md" component="form" onSubmit={submit}>
      <Stack gap="xs">
        <Title order={4}>New Character</Title>
        {error && <Text c="red" size="xs">{error}</Text>}
        <TextInput label="Name" required value={name} onChange={e=>setName(e.target.value)} />
        <TextInput label="Parrot AI Path" value={parrotPath} onChange={e=>setParrotPath(e.target.value)} />
        <Textarea label="Follow for more text" value={followText} onChange={e=>setFollowText(e.target.value)} minRows={2} />
        <TextInput label="Image Filename" value={imageFilename} onChange={e=>setImageFilename(e.target.value)} />
        <Group justify="flex-end" mt="sm">
          <Button type="submit" loading={submitting} disabled={submitting}>Add Character</Button>
        </Group>
      </Stack>
    </Card>
  );
};
