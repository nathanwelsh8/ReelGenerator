import { useEffect, useState } from 'react';
import { createProject, listProjects, enqueueVideo as enqueueVideoService, enqueueProjectProcessing as enqueueProjectProcessingService, reconcileProject as reconcileProjectService } from '../services/projectsService';
import { listCharacters } from '../services/charactersService';
import { uploadProjectToInstagram } from '../services/uploadService';
import type { Project } from '../types';
import { STATUSES, normalizeStatus } from '../utils/constants';
import { StatusBadge } from '../components/StatusBadge';
import { Link } from 'react-router-dom';
import { Container, Title, SimpleGrid, Card, Group, Stack, Text, Progress, Button, Select, TextInput, Textarea, Loader, Box } from '@mantine/core';
import { notifications } from '@mantine/notifications';

interface ProjectWithPct extends Project { pct: number }

export const Home = () => {
  const [projects, setProjects] = useState<ProjectWithPct[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
  const data: Project[] = await listProjects();
      setProjects(data.map(p => ({ ...p, pct: p.total_dialogues ? p.completed_dialogues / p.total_dialogues : 0 })));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed';
      setError(msg);
    }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={2}>Projects</Title>
      </Group>
      <NewProjectForm onCreated={load} />
      {loading && (
        <Group justify="center" mt="lg"><Loader /></Group>
      )}
      {error && <Text c="red" size="sm" mt="sm">{error}</Text>}
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md" mt="md">
        {projects.map(p => <ProjectCard key={p.id} project={p} refresh={load} />)}
      </SimpleGrid>
    </Container>
  );
};

// --- New Project Form ---
import { useState as useS } from 'react';
import type { Character } from '../types';

const NewProjectForm = ({ onCreated }: { onCreated: () => void }) => {
  const [title, setTitle] = useS('');
  const [caption, setCaption] = useS('');
  const [pdfUrl, setPdfUrl] = useS('');
  const [primary, setPrimary] = useS<number | ''>('');
  const [secondary, setSecondary] = useS<number | ''>('');
  const [characters, setCharacters] = useS<Character[]>([]);
  const [submitting, setSubmitting] = useS(false);
  const [err, setErr] = useS<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
  const chars = await listCharacters();
  setCharacters(chars);
      } catch (err) {
        /* ignore load characters error */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !pdfUrl.trim() || !primary || !secondary) { setErr('All required'); return; }
    setErr(null); setSubmitting(true);
    try {
  notifications.show({ id:'create-project', loading:true, title:'Creating project', message:'Submitting project...', autoClose: false, withCloseButton:false });
  await createProject({ title, caption, pdf_url: pdfUrl, primary_character_id: primary, secondary_character_id: secondary });
  notifications.update({ id:'create-project', loading:false, title:'Project created', message:'Project has been added', color:'green', autoClose:2000 });
      setTitle(''); setCaption(''); setPdfUrl(''); setPrimary(''); setSecondary('');
      onCreated();
    } catch (e) {
  const msg = e instanceof Error ? e.message : 'Failed';
  setErr(msg);
  notifications.update({ id:'create-project', loading:false, title:'Create failed', message:msg, color:'red', autoClose:4000 });
    }
    finally { setSubmitting(false); }
  };

  const selectData = characters.map(c => ({ value: String(c.id), label: c.name }));
  return (
    <Card withBorder radius="md" mb="lg" component="form" onSubmit={submit}>
      <Stack gap="xs">
        <Title order={4}>New Project</Title>
        {err && <Text c="red" size="xs">{err}</Text>}
        <TextInput label="Title" required value={title} onChange={e=>setTitle(e.target.value)} placeholder="Title *" />
        <Textarea label="Caption" value={caption} onChange={e=>setCaption(e.target.value)} minRows={2} />
        <TextInput label="PDF URL" required value={pdfUrl} onChange={e=>setPdfUrl(e.target.value)} placeholder="https://..." />
        <Group grow>
          <Select label="Primary" required data={selectData} value={primary ? String(primary) : null} onChange={v=>setPrimary(v? Number(v) : '')} searchable nothingFoundMessage="No characters" />
          <Select label="Secondary" required data={selectData} value={secondary ? String(secondary) : null} onChange={v=>setSecondary(v? Number(v) : '')} searchable nothingFoundMessage="No characters" />
        </Group>
        <Group justify="flex-end" mt="sm">
          <Button type="submit" loading={submitting} disabled={submitting}>Create Project</Button>
        </Group>
      </Stack>
    </Card>
  );
};

// --- Project Card ---
const ProjectCard = ({ project, refresh }: { project: ProjectWithPct; refresh: () => void }) => {
  const { id, title, status: rawStatus, video_url, pct, completed_dialogues, total_dialogues } = project;
  const status = normalizeStatus(rawStatus);

  const uploadToInstagram = async () => { 
    const nid = `upload-${id}`; 
    notifications.show({ id:nid, loading:true, title:'Uploading', message:'Uploading video to Instagram...', autoClose:false, withCloseButton:false });
    try { await uploadProjectToInstagram(id); notifications.update({ id:nid, loading:false, title:'Upload queued', message:'Instagram upload started', color:'green', autoClose:2500 }); refresh(); } 
    catch (e) { notifications.update({ id:nid, loading:false, title:'Upload failed', message: e instanceof Error ? e.message : 'Error', color:'red', autoClose:4000 }); }
  };
  const handleReconcile = async () => {
    const nid = `reconcile-${id}`;
    notifications.show({ id:nid, loading:true, title:'Reconciling', message:'Reconciling and queueing audio jobs…', autoClose:false, withCloseButton:false });
    try {
      // 1) Reconcile statuses (COMPLETED if audio exists; reset stuck INPROGRESS -> NEW)
      await reconcileProjectService(id);
      // 2) Enqueue NEW/FAILED dialogues to Higgs audio queue
      await enqueueProjectProcessingService(id);
      notifications.update({ id:nid, loading:false, title:'Reconciled + Queued', message:'Audio jobs enqueued', color:'green', autoClose:2000 });
      refresh();
    }
    catch (e) { notifications.update({ id:nid, loading:false, title:'Reconcile failed', message: e instanceof Error ? e.message : 'Error', color:'red', autoClose:4000 }); }
  };
  const retryRender = async () => {
    const nid = `render-${id}`;
    notifications.show({ id:nid, loading:true, title:'Retrying render', message:'Queueing video render...', autoClose:false, withCloseButton:false });
    try { await enqueueVideoService(id); notifications.update({ id:nid, loading:false, title:'Render queued', message:'Video render started', color:'green', autoClose:2000 }); refresh(); }
    catch (e) { notifications.update({ id:nid, loading:false, title:'Render retry failed', message: e instanceof Error ? e.message : 'Error', color:'red', autoClose:4000 }); }
  };
  const enqueueProject = async () => {
    const nid = `enqueue-${id}`;
    notifications.show({ id:nid, loading:true, title:'Enqueue project', message:'Submitting for processing...', autoClose:false, withCloseButton:false });
    try { await enqueueProjectProcessingService(id); notifications.update({ id:nid, loading:false, title:'Queued', message:'Project processing started', color:'green', autoClose:2000 }); refresh(); }
    catch (e) { notifications.update({ id:nid, loading:false, title:'Enqueue failed', message: e instanceof Error ? e.message : 'Error', color:'red', autoClose:4000 }); }
  };

  return (
    <Card withBorder radius="md" shadow="sm" padding="md">
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Stack gap={0} style={{ flex:1 }}>
            <Text fw={600} component={Link} to={`/projects/${id}`} style={{ textDecoration: 'none' }} c="white">
              {title}
            </Text>
            <Text size="xs" c="dimmed">ID: {id}</Text>
          </Stack>
          <StatusBadge status={rawStatus} />
        </Group>
        {status === STATUSES.IN_PROGRESS && (
          <Stack gap={4}>
            <Text size="xs" c="dimmed">{completed_dialogues}/{total_dialogues}</Text>
            <Progress value={Math.round(pct*100)} size="sm" radius="sm" />
            <Stack gap={4}>
              <Button size="xs" variant="outline" onClick={handleReconcile}>Reconcile</Button>
            </Stack>
          </Stack>
        )}
        {status === STATUSES.NEW && (
          <Stack gap={4}>
            <Text size="xs" c="dimmed">Awaiting processing</Text>
            <Button size="xs" onClick={enqueueProject}>Start Processing</Button>
          </Stack>
        )}
        {status === STATUSES.RENDERING && (
            <Stack gap={4}>
              <Text size="xs" c="dimmed">Video rendering in progress…</Text>
              <Button size="xs" variant="outline" onClick={retryRender}>Retry Render</Button>
            </Stack>
        )}
        {status === STATUSES.COMPLETED && (
          <Stack gap="xs">
            {video_url && (
              <Box>
                <video controls style={{ width:'100%', borderRadius:6 }} src={video_url} />
              </Box>
            )}
            <Button size="xs" variant="subtle" onClick={uploadToInstagram}>Upload to Instagram</Button>
          </Stack>
        )}
      </Stack>
    </Card>
  );
};
