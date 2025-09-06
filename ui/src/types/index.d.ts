import type { STATUSES } from '../utils/constants';

export type StatusKey = typeof STATUSES[keyof typeof STATUSES] | 'INPROGRESS' | 'UNKNOWN';

export interface Project {
  id: number;
  title: string;
  status: StatusKey;
  completed_dialogues: number;
  total_dialogues: number;
  video_url?: string | null;
  caption?: string;
  primary_character_id?: number;
  secondary_character_id?: number;
  created_at?: string;
}

// Dialogue as expected by UI after mapping backend DialogueOut
export interface Dialogue {
  id: number;
  line_number: number; // computed client-side (index)
  text: string;        // maps from 'sentence'
  status: string;      // backend status values
  audio_url?: string | null; // maps from 'audio'
  character?: string;
  character_id?: number | null;
  image?: string | null;
  image_search?: string | null;
}

export interface Character {
  id: number;
  name: string;
  image_path: string;
  parrot_ai_path: string;
  active: number; // 1 or 0 from backend
  follow_line?: string | null;
  follow_line_audio?: string | null;
  image_filename?: string; // when creating
}

export interface ApiListResponse<T> { data: T[] }
