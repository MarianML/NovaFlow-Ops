# NovaFlow Ops Web

This is the Next.js frontend for **NovaFlow Ops**.  
It provides a simple UI to create runs, execute UI steps, and inspect logs + screenshot artifacts served by the API.

## Run locally

```bash
cd apps/web
npm install
npm run dev

Open http://localhost:3000

Environment variables

Create apps/web/.env.local:

NEXT_PUBLIC_API_URL=http://localhost:8000
