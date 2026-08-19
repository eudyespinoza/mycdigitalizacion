FROM node:22-alpine AS base
WORKDIR /app
RUN corepack enable
COPY package.json ./
RUN pnpm install --no-frozen-lockfile
COPY . .

FROM base AS development

FROM base AS build
RUN pnpm build

FROM node:22-alpine AS production
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
