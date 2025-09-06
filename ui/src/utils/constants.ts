export const API_BASE = '/api';

// Canonical internal status keys
export const STATUSES = {
  NEW: 'NEW',
  IN_PROGRESS: 'IN_PROGRESS', // prefer underscore form internally
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  RENDERING: 'RENDERING',
  UPLOADED: 'UPLOADED'
} as const;

// Acceptable variants coming from backend (normalize to canonical keys above)
const STATUS_ALIASES: Record<string, keyof typeof STATUSES> = {
  INPROGRESS: STATUSES.IN_PROGRESS,
  IN_PROGRESS: STATUSES.IN_PROGRESS,
  NEW: STATUSES.NEW,
  COMPLETED: STATUSES.COMPLETED,
  FAILED: STATUSES.FAILED,
  RENDERING: STATUSES.RENDERING,
  UPLOADED: STATUSES.UPLOADED
};

export function normalizeStatus(raw: string | undefined | null): keyof typeof STATUSES | 'UNKNOWN' {
  if (!raw) return 'UNKNOWN';
  const upper = raw.toUpperCase();
  return STATUS_ALIASES[upper] || 'UNKNOWN';
}

export function displayStatus(raw: string): string {
  const norm = normalizeStatus(raw);
  if (norm === 'UNKNOWN') return raw;
  return norm.replace('_', ' ');
}

export const STATUS_COLORS: Record<string,string> = {
  [STATUSES.NEW]: 'var(--color-accent)',
  [STATUSES.IN_PROGRESS]: 'var(--color-warning)',
  [STATUSES.COMPLETED]: 'var(--color-success)',
  [STATUSES.FAILED]: 'var(--color-danger)',
  [STATUSES.RENDERING]: 'var(--color-accent-hover)',
  UNKNOWN: '#555'
};
