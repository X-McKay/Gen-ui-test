# AI Governance Intake — frontend (Next.js 16 + CopilotKit runtime).
#
#   docker build -t intake-frontend frontend
#   docker run --rm -p 3000:3000 -e BACKEND_URL=http://backend:8000 intake-frontend
#
# next.config.ts does not set `output: "standalone"`, so the image runs `next start` with the
# full node_modules. Switching the config to standalone would allow a much smaller runtime
# stage (copy .next/standalone + .next/static and run `node server.js`); see README.md.

ARG NODE_IMAGE=node:22-alpine

# ---- deps: install with the pinned pnpm from package.json#packageManager ----------------
FROM ${NODE_IMAGE} AS deps
RUN corepack enable && corepack prepare pnpm@11.21.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# ---- build: next build. BACKEND_URL is read at request time by the /api/backend and
# /api/copilotkit route handlers, so nothing backend-specific is baked into the build. ----
FROM deps AS build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
COPY . .
RUN pnpm build

# ---- runtime: next start as a non-root user ---------------------------------------------
FROM ${NODE_IMAGE} AS runtime
RUN corepack enable && corepack prepare pnpm@11.21.0 --activate
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/package.json /app/next.config.ts ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next ./.next
USER node
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD wget -qO /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["pnpm", "start"]
