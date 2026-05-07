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
