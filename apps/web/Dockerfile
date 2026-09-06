FROM node:22-alpine AS deps

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app/apps/web

ARG VITE_API_BASE_URL=/api
ARG VITE_BASE_PATH=/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_BASE_PATH=$VITE_BASE_PATH

COPY --from=deps /app/apps/web/node_modules ./node_modules
COPY apps/web ./

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app/apps/web

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/apps/web/.output ./.output
COPY --from=builder /app/apps/web/public ./public

EXPOSE 3000

CMD ["npm", "run", "start"]
