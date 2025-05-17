# USD Asset Analysis Web Application

This web application provides analysis of USD (Universal Scene Description) assets and their dependencies.

## Features

- Analyze USD asset references and textures
- Batch submission support
- Detailed dependency visualization
- Modern web interface

## Tech Stack

### Frontend
- React.js + TypeScript
- Next.js (SSR framework)
- Tailwind CSS + Shadcn/ui
- React Query
- React Dropzone
- Axios

### Backend
- Python FastAPI
- Uvicorn
- USD Core
- Celery
- Redis
- PostgreSQL (optional)

### Infrastructure
- Docker
- Nginx

## Development Setup

1. Install dependencies
2. Configure environment variables
3. Start development servers

## Project Structure

```
usd_web/
├── frontend/           # Next.js frontend application
├── backend/           # FastAPI backend application
├── docker/           # Docker configuration files
└── docs/             # Project documentation
```
