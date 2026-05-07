using './main.bicep'

param appName = 'heavyuse'
param sqlAdminLogin = 'heavyuse-admin'

// Set these env vars before deploying:
//   export SQL_ADMIN_PASSWORD='...'   # first deploy only — omit once AAD-only auth is enabled
//   export AAD_ADMIN_LOGIN='<email>'
//   export AAD_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
//   export DEVELOPER_IP=$(curl -s https://checkip.amazonaws.com)
//   export GOOGLE_TAG_ID='...'
//   export DJANGO_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
//   export CLOUDFLARE_ORIGIN_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
//   export FLICKR_KEY='...'
//   export FLICKR_SECRET='...'
//   export FACEBOOK_CLIENT_ID='...'
//   export FACEBOOK_SECRET='...'
//   export DISCORD_CLIENT='...'
//   export DISCORD_SECRET='...'
//   export DISCORD_KEY='...'
param sqlAdminPassword = readEnvironmentVariable('SQL_ADMIN_PASSWORD', '')
param developerIp = readEnvironmentVariable('DEVELOPER_IP', '')
param aadAdminLogin = readEnvironmentVariable('AAD_ADMIN_LOGIN', '')
param aadAdminObjectId = readEnvironmentVariable('AAD_OBJECT_ID', '')
param googleTagId = readEnvironmentVariable('GOOGLE_TAG_ID', '')
param hostname = 'heavyuse.us'

param appSecrets = {
  DJANGO_SECRET_KEY: readEnvironmentVariable('DJANGO_SECRET_KEY', '')
  CLOUDFLARE_ORIGIN_SECRET: readEnvironmentVariable('CLOUDFLARE_ORIGIN_SECRET', '')
  FLICKR_KEY: readEnvironmentVariable('FLICKR_KEY', '')
  FLICKR_SECRET: readEnvironmentVariable('FLICKR_SECRET', '')
  FACEBOOK_CLIENT_ID: readEnvironmentVariable('FACEBOOK_CLIENT_ID', '')
  FACEBOOK_SECRET: readEnvironmentVariable('FACEBOOK_SECRET', '')
  DISCORD_CLIENT: readEnvironmentVariable('DISCORD_CLIENT', '')
  DISCORD_SECRET: readEnvironmentVariable('DISCORD_SECRET', '')
  DISCORD_KEY: readEnvironmentVariable('DISCORD_KEY', '')
}
