# Brainrot Factory UI

A lightweight React + Vite + TypeScript interface for managing projects, dialogues, and characters.

## Scripts
- `npm run dev` – start dev server
- `npm run build` – production build
- `npm run preview` – preview production build
- `npm run lint` – run ESLint
- `npm test` – run vitest

## Env / Config
API requests are proxied to `http://localhost:8000` via Vite dev server (`/api`). Adjust `vite.config.ts` if backend runs elsewhere.

## Features (initial scaffold)
- Projects list w/ creation form, progress, upload & requeue actions
- Dialogues table per project with retry and audio playback
- Characters listing with creation form & follow audio requeue

Further enhancements: global error toasts, pagination, optimistic updates, skeleton loaders, auth.
