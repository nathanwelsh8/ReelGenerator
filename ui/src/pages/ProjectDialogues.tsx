import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import type { Dialogue, Project } from '../types';
import { normalizeStatus, STATUSES } from '../utils/constants';
import { StatusBadge } from '../components/StatusBadge';
import { getProject } from '../services/projectsService';
import { listDialogues } from '../services/dialoguesService';
import { Container, Title, Card, Table, Text, Loader, Group } from '@mantine/core';

export const ProjectDialogues = () => {
  const { id } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [dialogues, setDialogues] = useState<Dialogue[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
  const pr = await getProject(id); setProject(pr);
  const mapped = await listDialogues(id);
  setDialogues(mapped);
    } finally { setLoading(false); }
  }, [id]);
  useEffect(()=>{ load(); }, [load]);

  // Action column removed (no per-dialogue retry UI requested)

  return (
    <Container size="lg" py="md">
      <Title order={2} mb="sm">Project Dialogues</Title>
      {project && <Text size="sm" c="dimmed" mb="md">{project.title} – {project.status}</Text>}
      {loading && <Group justify="center" my="lg"><Loader /></Group>}
      {!loading && (
        <Card withBorder radius="md">
          <Table striped highlightOnHover withTableBorder withColumnBorders fz="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>#</Table.Th>
                <Table.Th style={{ width:'40%' }}>Text</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Audio</Table.Th>
                {/* Action column removed */}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {dialogues.map(d => (
                <Table.Tr key={d.id}>
                  <Table.Td>{d.line_number}</Table.Td>
                  <Table.Td style={{ maxWidth:400 }}>{d.text}</Table.Td>
                  <Table.Td><StatusBadge status={d.status} /></Table.Td>
                  <Table.Td>{d.audio_url && normalizeStatus(d.status) === STATUSES.COMPLETED && <audio controls src={d.audio_url} />}</Table.Td>
                  {/* Per-dialogue action cell removed */}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}
    </Container>
  );
};
