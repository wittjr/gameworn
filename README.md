Django web site to display sports memorabilia collections. Still in progress but key features aim to be:
* Display your collection (community tends to use sites like smugmug and flikr currently)
* Browse other collections
* Search for players/teams/etc from other collections
* Allow owners to mark items as for sale/trade
* Let users create a want list
* Try to assist in maintaining provinence of items (users can mark items as transferred to others)
* Getty images integration to help photomatch items (might be too pricey)


Inspiration from collections I've seen:
* https://www.sinbinsweaters.com
* https://libertybelljerseys.com

---

## Azure Deployment

The app runs on Azure App Service (Linux, Python 3.13) backed by Azure SQL Database, with secrets stored in Key Vault. Traffic is routed through Cloudflare.

### First-time infrastructure setup

#### Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`)
- [sqlcmd](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/go-sqlcmd-utility) installed (`brew install sqlcmd`)

#### 1. Create the resource group

```bash
az group create --name heavyuse-rg --location westus3
```

#### 2. Set environment variables

```bash
export SQL_ADMIN_PASSWORD='...'           # strong password of your choice
export AAD_ADMIN_LOGIN='me@example.com'  # your Azure AD email
export AAD_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
export DEVELOPER_IP=$(curl -s https://checkip.amazonaws.com)
export GOOGLE_TAG_ID='G-XXXXXXXXXX'
export DJANGO_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
export CLOUDFLARE_ORIGIN_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
export FLICKR_KEY='...'
export FLICKR_SECRET='...'
export FACEBOOK_CLIENT_ID='...'
export FACEBOOK_SECRET='...'
export DISCORD_CLIENT='...'
export DISCORD_SECRET='...'
export DISCORD_KEY='...'
```

#### 3. Deploy the infrastructure

```bash
az deployment group create \
  --resource-group heavyuse-rg \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

#### 4. Grant the App Service access to the database

This is a one-time step. The App Service uses a managed identity to authenticate to SQL Server, but SQL Server also needs a matching database user created manually.

Open the Azure portal, navigate to **SQL databases → heavyuse-db → Query editor (preview)**, log in with your Azure AD account, and run:

```sql
CREATE USER [heavyuse] FROM EXTERNAL PROVIDER;
ALTER ROLE db_owner ADD MEMBER [heavyuse];
```

Alternatively, if `sqlcmd` is working with your Azure AD account:

```bash
sqlcmd -S heavyuse-sql.database.windows.net \
       -d heavyuse-db \
       --authentication-method=ActiveDirectoryInteractive \
       --tenant-id $(az account show --query tenantId -o tsv) \
       -U me@example.com \
       -Q "CREATE USER [heavyuse] FROM EXTERNAL PROVIDER; ALTER ROLE db_owner ADD MEMBER [heavyuse];"
```

---

### Deploying code

Run these steps whenever you want to push a new version:

#### 1. Build and upload the zip

```bash
zip -r deploy.zip . \
  --exclude "./.env" \
  --exclude "*.pyc" \
  --exclude "./.git/*" \
  --exclude "./__pycache__/*" \
  --exclude "./*.sqlite3" \
  --exclude "./backups/*" \
  --exclude "./node_modules/*"

az webapp deployment source config-zip \
  --resource-group heavyuse-rg \
  --name heavyuse \
  --src deploy.zip
```

The deployment triggers an Oryx build on the server that installs all Python dependencies (including the Azure SQL driver from `requirements-azure.txt`).

#### 2. Run migrations

Once the deployment completes and the app is running, SSH in:

```bash
az webapp ssh --resource-group heavyuse-rg --name heavyuse
```

Inside the SSH session, find the current app directory (path changes per deployment) and run:

```bash
APP_DIR=$(ls -dt /tmp/8de* 2>/dev/null | head -1 || echo /home/site/wwwroot)
cd $APP_DIR
source antenv/bin/activate
python manage.py migrate
```

#### 3. Load fixtures (first deploy only)

```bash
python manage.py loaddata leagues game_types gear_types usage_types coa_types how_obtained_options externalresources teams season_sets auth_sources
```

---

### Updating infrastructure settings

If you change `infra/main.bicep` or `infra/main.bicepparam` (e.g. adding a secret, changing an app setting), re-run the infrastructure deploy:

```bash
az deployment group create \
  --resource-group heavyuse-rg \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

No code redeploy is needed for settings-only changes — the App Service restarts automatically.

---

### Cloudflare setup

Point your domain at the App Service:

1. In Cloudflare DNS, add a CNAME record: `heavyuse.us` → `heavyuse.azurewebsites.net`, proxied.
2. Set SSL/TLS mode to **Full** (not Full Strict).
3. Add the custom domain in Azure: **App Service → Custom domains → Add custom domain**.
4. To enforce that traffic must come through Cloudflare, configure `CLOUDFLARE_ORIGIN_SECRET` (already in Key Vault) and inject it on every request using a Cloudflare Worker or Transform Rule that adds the `X-Origin-Secret` header.


## Agent Framework from https://github.com/dralgorhythm/claude-agentic-framework

### Commands

Single-agent expert modes, invoked via slash commands, backed by skills in `.claude/skills/`:

| Command | Role |
|---------|------|
| `/architect` | System design, ADRs |
| `/builder` | Implementation, debugging, testing |
| `/qa-engineer` | Test strategy, E2E, accessibility |
| `/security-auditor` | Threat modeling, security audits |
| `/ui-ux-designer` | Interface design, visual assets |
| `/code-check` | SOLID, DRY, consistency audit |

### Swarm Orchestrators

Multi-agent commands that fan work out across parallel workers:

| Command | What It Does |
|---------|-------------|
| `/swarm-plan` | Launches 3-6 explorer agents to research patterns, dependencies, and constraints — produces a decomposed plan |
| `/swarm-execute` | Picks up planned work, fans out across builder agents (up to 8 parallel), each running quality gates |
| `/swarm-review` | Launches 5 parallel reviewers (security, performance, architecture, tests, quality) — run 2-3 times |
| `/swarm-research` | Deep multi-source investigation with verification tiers |

All 12 workflow skills — `/architect`, `/builder`, `/qa-engineer`, `/security-auditor`, `/ui-ux-designer`, `/code-check`, `/land-the-plane`, `/tailor`, `/swarm-plan`, `/swarm-execute`, `/swarm-review`, and `/swarm-research` — carry `disable-model-invocation: true`: only a user typing the slash name can invoke them. The four role skills (`/architect`, `/qa-engineer`, `/security-auditor`, `/ui-ux-designer`) are user-invoked entry points: `/architect` delegates methodology to the always-on `designing-systems` and `writing-adrs` library skills, and the others carry their procedures inline or lean on the always-loaded rules (`security.md`, `debugging-protocol.md`) — so gating them costs nothing that auto-discovery needed.

### The Full Cycle

```
/architect <feature>  →  /swarm-plan  →  /swarm-execute  →  /swarm-review (2-3x)  →  PR
```

One agent thinks. Many agents build. Many agents review.

### Workers

Five specialized agent types tuned for cost and capability:

| Worker | Use |
|--------|-----|
| `worker-explorer` | Fast codebase search, web research, dependency mapping |
| `worker-builder` | Implementation, testing, refactoring |
| `worker-reviewer` | Code review, security analysis |
| `worker-research` | Deep multi-source investigation |
| `worker-architect` | Complex design decisions, ADRs |

Model tiers are pinned in each agent's frontmatter (`.claude/agents/`) — that is the single source of truth.

### Skills

9 library skills across 5 categories — discovered natively from each skill's description, no hook or registry required:

**Architecture** · **Core Engineering** · **Operations** · **Product** · **Security**

A deliberately lean catalog: high-value, single-responsibility skills that don't duplicate what the model already knows, from `designing-systems` and `testing` to `swarm-coordination` and `threat-modeling`. Generic-knowledge skills (API textbook patterns, OWASP lists, WCAG tables) were retired in the 2026-07 rationalization after base-model evals showed current models produce that content unaided — evidence in [artifacts/evals_catalog_rationalization.md](artifacts/evals_catalog_rationalization.md). See [docs/skills.md](docs/skills.md) for the full list.

Catalog size is a defended design decision, not an oversight. Every skill's name and description loads into every session's context regardless of relevance, and the skill-listing context budget is shared across *everything* an adopter has installed — this framework's skills plus their own. Growing the catalog without discipline degrades discovery for every skill sharing that budget, including ones this repo didn't add. New skill proposals go through CONTRIBUTING.md's eval-first bar, not "this seems useful."

Measured 2026-07: after gating the 12 workflow skills (`disable-model-invocation: true`), only the 9 library skills are ungated and auto-discoverable, at roughly ~0.9k tokens of always-loaded listing — against a ~2k-token listing budget on 200K-context sessions (~10k on 1M-context sessions). Separately, CLAUDE.md (104 lines) plus `.claude/rules/` (409 lines) run roughly ~5k tokens of always-loaded instructions — a different budget line item from the skill listing. Both numbers move as the platform and catalog change; run `/doctor` to check for dropped or truncated skill descriptions and `/context` to see live context-window consumption on your own setup rather than trusting a static figure.

### Safety Hooks

Pre-configured hooks that run automatically:

- **Secret detection** — blocks commits containing API keys, tokens, private keys
- **Protected files** — prevents accidental modification of `.env`, `.mcp.json`
- **Push blocking** — stops direct pushes to `main`/`master`
- **Dangerous command guard** — warns on `rm -rf`, force push, `terraform destroy`
- **File locking** — prevents concurrent edits in multi-agent swarms

What ships enabled: format, warn, and guard hooks, all fail-soft (a missing `jq` or unparseable input skips the check rather than blocking). Secret-bearing paths and destructive commands are denied at the permission layer (`permissions.deny`), not just warned about by a hook. See [docs/hooks.md#security-model](docs/hooks.md#security-model) for what hooks can and cannot guarantee.

### MCP Servers

Four servers pre-configured in `.mcp.json`:

| Server | Purpose |
|--------|---------|
| Sequential Thinking | Structured multi-step reasoning |
| Chrome DevTools | Browser testing, performance profiling |
| Context7 | Up-to-date library documentation |
| Filesystem | File operations beyond workspace |

## Customization

Everything is designed to be extended:

- Add command-style skills → `.claude/skills/your-skill/SKILL.md` (add `disable-model-invocation: true` for side-effecting workflows)
- Add skills → `.claude/skills/category/your-skill/SKILL.md`
- Add rules → `.claude/rules/your-rule.md`
- Add hooks → `.claude/hooks/your-hook.sh`
- Add workers → `.claude/agents/worker-yourtype.md`

Templates for each are in `.claude/templates/`.
