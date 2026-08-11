# Tech Strategy - Golden Paths (Customize for Your Project)

This is the **SINGLE SOURCE OF TRUTH** for technology choices.

## Customization Required

**IMPORTANT**: This file contains example technology choices. Customize it for your project.

Replace the Golden Paths below with your actual tech stack. The framework enforces whatever you put here.

## Compliance

1. **Follow This File**: Use the technologies listed in the Golden Paths below
2. **No Deviations**: Do not suggest alternatives unless explicitly instructed
3. **Latest Stable**: Always use the latest stable version unless pinned

## Language Golden Paths

### Python

| Component | Choice |
|-----------|--------|
| Runtime | Python 3.14+ |
| Frontend | Tailwind, Flowbite |
| Framework | Django |
| Tooling | Makefile |

## Infrastructure

| Component | Choice |
|-----------|--------|
| Agile/PoC | PythonAnywhere (PaaS) |
| Production | Azure (App Service) |
| Edge/CDN | Cloudflare |
| Secrets | Azure Key Vault via Bicep |

## Data

| Component | Choice |
|-----------|--------|
| Relational (OLTP) | SQLite3 (Local), MySQL (UAT), MSSQL (Prod) |
| Object Storage | FileSystemStorage(dev), FileSystemStorage (UAT), Azure Storage (Prod) |

## Observability

| Component | Choice |
|-----------|--------|
| Standard | OpenTelemetry (OTel) |
| SDK | azure-monitor-opentelemetry (direct export, no collector) |
| Dashboard | Azure Monitor / Application Insights (Prod) |

## Authentication

| Component | Choice |
|-----------|--------|
| Framework | django-allauth |
| Social Login | Discord OAuth |

## CI/CD

| Component | Choice |
|-----------|--------|
| Platform | GitHub Actions |
| Deploy Auth | Publish profile (`AZURE_PUBLISH_PROFILE`) |
| Security | Trivy |

## Graduated Hosting Strategy

1. **UAT Tier** (PoC/MVP): PythonAnywhere - fast iteration, low cost, limited scale
2. **Production Tier** (Scale): Azure - high scale, high reliability, full control
