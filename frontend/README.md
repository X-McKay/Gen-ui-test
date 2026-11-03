# Frontend

The Next.js app for the intake assistant. How to run, test and extend it is documented in the
[root README](../README.md); this directory holds only the app.

`pnpm dev` needs `BACKEND_URL` (the FastAPI origin, e.g. `http://127.0.0.1:8000`) because `/api/backend/*`
is proxied to it.

| Script                                       | What it does                                                        |
| -------------------------------------------- | ------------------------------------------------------------------- |
| `pnpm dev` / `pnpm build` / `pnpm start`     | Next.js dev server, production build, production server (port 3000) |
| `pnpm typecheck` / `pnpm lint`               | `tsc --noEmit`, eslint                                              |
| `pnpm format` / `pnpm format:check`          | Prettier write / check                                              |
| `pnpm test`                                  | Vitest unit tests (`*.test.ts(x)` beside their subjects)            |
| `pnpm e2e` / `pnpm e2e:ui` / `pnpm e2e:live` | Playwright suites, see [e2e/README.md](e2e/README.md)               |
| `pnpm gen:types`                             | Regenerates `lib/intakeTypes.ts` from `schema/intake.schema.json`   |
