# Developer documentation image. Three stages:
#   1. reference: read the Python source and write the reference pages (no project code runs).
#   2. site:      build the Docusaurus site with the pinned lock file.
#   3. runtime:   serve the static files with unprivileged nginx on port 8080.
# Build from the repository root: docker build -f docs/Dockerfile .

FROM python:3.13-slim AS reference
WORKDIR /repo
ARG DOCS_SOURCE_REF=main
COPY apps ./apps
COPY config ./config
COPY manage.py ./
COPY docs/scripts ./docs/scripts
COPY docs/openapi ./docs/openapi
RUN python docs/scripts/generate_reference.py --ref "$DOCS_SOURCE_REF" --output /generated/docs --static /generated/static

FROM node:22-bookworm-slim AS site
WORKDIR /site
ARG DOCS_URL=https://localhost
ENV DOCS_URL=${DOCS_URL} \
    DO_NOT_TRACK=1 \
    DOCUSAURUS_TELEMETRY_DISABLED=1
# Install first. This layer is cached until the lock file changes.
COPY docs/package.json docs/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY docs/ ./
COPY --from=reference /generated/docs ./docs/reference/generated
COPY --from=reference /generated/static ./static
RUN npx docusaurus build

FROM python:3.13-slim AS headers
COPY docs/scripts/csp_hashes.py /csp_hashes.py
COPY --from=site /site/build /build
RUN python /csp_hashes.py /build /security-headers.conf

FROM nginx:1.28-alpine AS runtime
COPY docs/nginx.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=headers /security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=site /site/build/ /usr/share/nginx/html/docs/
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
