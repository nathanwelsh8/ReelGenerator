import { api } from './apiClient';
import type { Character } from '../types';
import { API_BASE } from '../utils/constants';

export interface CreateCharacterInput {
  name: string;
  parrot_ai_path: string;
  image_filename?: string;
  active: boolean;
  follow_line?: string | null;
}

export async function listCharacters(): Promise<Character[]> {
  const res = await api.get('/characters');
  const list: Character[] = res.data.data || res.data || [];
  const base = API_BASE.replace(/\/$/, '');
  return list.map(c => {
    let follow_line_audio = c.follow_line_audio;
    if (follow_line_audio && !follow_line_audio.startsWith('http')) {
      follow_line_audio = `${base}/${follow_line_audio.replace(/^\//,'')}`;
    }
    return { ...c, follow_line_audio };
  });
}

export async function createCharacter(input: CreateCharacterInput): Promise<Character> {
  const res = await api.post('/characters', input);
  return res.data.data || res.data;
}

export async function generateFollowAudio(characterId: number) {
  return api.post(`/characters/${characterId}/follow-audio`);
}
