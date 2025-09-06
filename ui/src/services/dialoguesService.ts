import { api } from './apiClient';
import type { Dialogue } from '../types';
import { API_BASE } from '../utils/constants';

export async function listDialogues(projectId: string | number): Promise<Dialogue[]> {
  const res = await api.get('/dialogues', { params: { project_id: projectId } });
  const raw: Array<{ id:number; sentence:string; status:string; character?:string; character_id?:number; audio?:string; image?:string; image_search?:string; }> = res.data.data || res.data || [];
  return raw.map((d, idx) => {
    let audio_url: string | null = d.audio || null;
    if (audio_url) {
      // Ensure leading API base so request hits backend (which is reverse proxied under /api)
      const base = API_BASE.replace(/\/$/, '');
      // Strip any leading slash from stored path then prefix with base
      if (!audio_url.startsWith('http')) {
        audio_url = `${base}/${audio_url.replace(/^\//,'')}`;
      }
    }
    return {
      id: d.id,
      line_number: idx + 1,
      text: d.sentence,
      status: d.status,
      audio_url,
      character: d.character,
      character_id: d.character_id ?? null,
      image: d.image ?? null,
      image_search: d.image_search ?? null
    } as Dialogue;
  });
}
