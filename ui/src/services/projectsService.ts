import { api } from './apiClient';
import type { Project } from '../types';

export interface CreateProjectInput {
  title: string;
  caption?: string;
  pdf_url: string;
  primary_character_id: number;
  secondary_character_id: number;
}

export async function listProjects(): Promise<Project[]> {
  const res = await api.get('/projects');
  return res.data.data || res.data || [];
}

export async function getProject(id: string | number): Promise<Project> {
  const res = await api.get(`/projects/${id}`);
  return res.data.data || res.data;
}

export async function createProject(input: CreateProjectInput): Promise<Project> {
  const res = await api.post('/projects', input);
  return res.data.data || res.data;
}


export async function enqueueProjectProcessing(projectId: number) {
  return api.post(`/process/project/${projectId}`);
}

export async function reconcileProject(projectId: number) {
  return api.post(`/process/project/${projectId}/reconcile`);
}

export async function enqueueVideo(projectId: number) {
  return api.post(`/process/project/${projectId}/enqueue-video`);
}
