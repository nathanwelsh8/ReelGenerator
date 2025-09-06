import { api } from './apiClient';

export async function uploadProjectToInstagram(projectId: number) {
  return api.post(`/upload/project/${projectId}`);
}
