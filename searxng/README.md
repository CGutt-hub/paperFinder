# SearXNG for Paper Finder

This directory contains the SearXNG deployment configuration for Paper Finder's web search functionality.

## Setup

1. **Install Docker** (if not already installed)
   - Download from: https://www.docker.com/products/docker-desktop

2. **Generate a secret key**
   ```bash
   openssl rand -hex 32
   ```
   Replace `changeme` in `settings.yml` with the generated key.

3. **Start SearXNG**
   ```bash
   cd searxng
   docker-compose up -d
   ```

4. **Access SearXNG**
   - Local: http://localhost:8080
   - API: http://localhost:8080/search?q=query&format=json

## Configuration

- `docker-compose.yml`: Docker container setup
- `settings.yml`: SearXNG configuration (engines, UI, privacy settings)

## Deployment

For production deployment:
- Use a reverse proxy (nginx/caddy) with HTTPS
- Set proper `SEARXNG_BASE_URL` in docker-compose.yml
- Change the secret key in settings.yml
- Consider hosting on: Render, Railway, fly.io, or your own server

## Integration

The Paper Finder static site connects to SearXNG via its JSON API at `/search?q=query&format=json&categories=science`
