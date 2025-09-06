import { Badge } from '@mantine/core';
import { normalizeStatus, displayStatus, STATUSES } from '../utils/constants';
import React from 'react';

// Mantine color mapping (can be themed later)
const STATUS_MANTINE_COLORS: Record<string, string> = {
  [STATUSES.NEW]: 'blue',
  [STATUSES.IN_PROGRESS]: 'yellow',
  [STATUSES.COMPLETED]: 'green',
  [STATUSES.FAILED]: 'red',
  [STATUSES.RENDERING]: 'indigo',
  [STATUSES.UPLOADED]: 'teal',
  UNKNOWN: 'gray'
};

export const StatusBadge: React.FC<{ status: string; size?: 'xs' | 'sm' | 'md'; }> = ({ status, size='xs' }) => {
  const norm = normalizeStatus(status);
  const label = displayStatus(norm);
  const color = STATUS_MANTINE_COLORS[norm] || STATUS_MANTINE_COLORS.UNKNOWN;
  return <Badge color={color} size={size} variant="filled" radius="sm" tt="uppercase" fw={500}>{label}</Badge>;
};
