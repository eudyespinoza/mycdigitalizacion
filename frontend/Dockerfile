FROM node:22-alpine AS base
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/package.json
RUN pnpm install --frozen-lockfile
COPY frontend frontend
WORKDIR /app/frontend

FROM base AS development

FROM base AS build
ARG API_INTERNAL_URL=http://backend:8000/api/v1
ARG API_PROXY_TARGET=http://backend:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ENV API_PROXY_TARGET=$API_PROXY_TARGET
RUN pnpm build

FROM node:22-alpine AS production
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/frontend/.next/standalone ./
WORKDIR /app/frontend
COPY --from=build /app/frontend/.next/static ./.next/static
COPY --from=build /app/frontend/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
