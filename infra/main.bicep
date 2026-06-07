@description('Base name used for all resources (e.g. "gameworn"). Must be globally unique for SQL and App Service.')
param appName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('SQL administrator username.')
param sqlAdminLogin string

@description('SQL administrator password. Required on first deploy to create the server. Leave empty on subsequent deploys once AAD-only auth is enabled — passing it after that causes a deployment failure.')
@secure()
param sqlAdminPassword string = ''

@description('Your local IP address to allow SQL access during setup. Leave empty to skip.')
param developerIp string = ''

@description('Azure AD login name for the SQL server admin (e.g. your email address).')
param aadAdminLogin string

@description('Azure AD object ID for the SQL server admin. Run: az ad signed-in-user show --query id -o tsv')
param aadAdminObjectId string

@description('All application secrets. Each key becomes an environment variable and a Key Vault secret (underscores converted to hyphens).')
@secure()
param appSecrets object

@description('Google Tag Manager ID. Not a secret — appears in page source.')
param googleTagId string = ''

@description('Custom domain for the app (e.g. heavyuse.us). Sets ALLOWED_HOSTS in Django.')
param hostname string

// ─── Cloudflare IP Ranges ─────────────────────────────────────────────────────
// Source: https://www.cloudflare.com/ips/  — update if Cloudflare publishes new ranges
var cloudflareRanges = [
  '173.245.48.0/20'
  '103.21.244.0/22'
  '103.22.200.0/22'
  '103.31.4.0/22'
  '141.101.64.0/18'
  '108.162.192.0/18'
  '190.93.240.0/20'
  '188.114.96.0/20'
  '197.234.240.0/22'
  '198.41.128.0/17'
  '162.158.0.0/15'
  '104.16.0.0/13'
  '104.24.0.0/14'
  '172.64.0.0/13'
  '131.0.72.0/22'
  '2400:cb00::/32'
  '2606:4700::/32'
  '2803:f800::/32'
  '2405:b500::/32'
  '2405:8100::/32'
  '2a06:98c0::/29'
  '2c0f:f248::/32'
]

var cfRestrictions = [for (cidr, i) in cloudflareRanges: {
  ipAddress: cidr
  action: 'Allow'
  priority: 100 + i
  name: 'Cloudflare-${i + 1}'
}]

var ipRestrictions = developerIp != '' ? concat(cfRestrictions, [{
  ipAddress: '${developerIp}/32'
  action: 'Allow'
  priority: 200
  name: 'Developer'
}]) : cfRestrictions

// ─── App Settings ─────────────────────────────────────────────────────────────
var plainAppSettings = [
  { name: 'DJANGO_SETTINGS_MODULE',          value: 'gameworn.settings' }
  { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
  { name: 'ENABLE_ORYX_BUILD',             value: 'true' }
  { name: 'DISABLE_COLLECTSTATIC',         value: 'true' }
  { name: 'PRE_BUILD_COMMAND',             value: 'cat requirements-azure.txt >> requirements.txt' }
  { name: 'AZURE_SQL_SERVER',                value: sqlServer.properties.fullyQualifiedDomainName }
  { name: 'AZURE_SQL_DATABASE',              value: sqlDbBasic.name }
  { name: 'AZURE_SQL_AUTHENTICATION',        value: 'ActiveDirectoryMsi' }
  { name: 'AZURE_STORAGE_ACCOUNT_NAME',      value: storageAccount.name }
  { name: 'DEVELOPER_IP',                    value: developerIp }
  { name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS', value: '3' }
  { name: 'PIP_CACHE_DIR',                     value: '/home/pip-cache' }
  { name: 'WEBSITE_VNET_ROUTE_ALL',             value: '1' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
  { name: 'GOOGLE_TAG_ID',                   value: googleTagId }
  { name: 'HOSTNAME',                        value: hostname }
]

// Only provision secrets that actually have a value. Unset secrets default to ''
// in main.bicepparam; skipping them avoids re-adding empty app settings (e.g. an
// unset FACEBOOK_CLIENT_ID) that would otherwise register an unconfigured provider.
var nonEmptySecrets = filter(items(appSecrets), item => !empty(item.value))

// Each key in appSecrets becomes an env var whose value is a Key Vault reference.
// KV secret name = key lowercased with underscores replaced by hyphens.
var kvBaseUri = 'https://${appName}-kv${environment().suffixes.keyvaultDns}/secrets/'
var secretAppSettings = [for item in nonEmptySecrets: {
  name: item.key
  value: '@Microsoft.KeyVault(SecretUri=${kvBaseUri}${toLower(replace(item.key, '_', '-'))}/)'
}]

// ─── App Service Plan ────────────────────────────────────────────────────────
resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${appName}-plan'
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
}

// ─── App Service ─────────────────────────────────────────────────────────────
resource app 'Microsoft.Web/sites@2023-01-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientCertEnabled: true
    clientCertMode: 'Optional'
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.13'
      appCommandLine: 'bash startup.sh'
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: ipRestrictions
      scmIpSecurityRestrictionsUseMain: false
      appSettings: concat(plainAppSettings, secretAppSettings)
    }
  }
}

// ─── SQL Server ──────────────────────────────────────────────────────────────
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: '${appName}-sql'
  location: location
  properties: union(
    {
      administratorLogin: sqlAdminLogin
      minimalTlsVersion: '1.2'
    },
    sqlAdminPassword != '' ? { administratorLoginPassword: sqlAdminPassword } : {}
  )
}

// ─── SQL Database (legacy 32 MB Free SKU — being retired) ────────────────────
// Kept temporarily so existing data can be migrated to sqlDbFreeOffer below.
// Once migrated and AZURE_SQL_DATABASE points at the new DB, delete this block.
resource sqlDb 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: '${appName}-db'
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    freeLimitExhaustionBehavior: 'AutoPause'
  }
}

// ─── SQL Database (Basic DTU tier) ───────────────────────────────────────────
// Basic: 5 DTU, 2 GB max storage, flat ~$5/month, always-on.
// Migrated off the serverless Free Offer (GP_S_Gen5_2): the workload is near-idle
// (~1% CPU) but the 0.5 vCore active-time floor burned through the free
// 100,000 vCore-seconds/month and triggered overages. Basic's flat rate is far
// cheaper for this usage and removes serverless cold starts.
// NOTE: the resource name stays '${appName}-db-free' so the existing database is
// converted in place, preserving its data. Renaming would drop-and-recreate it.
resource sqlDbBasic 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: '${appName}-db-free'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    maxSizeBytes: 2147483648 // 2 GB — Basic tier maximum
  }
}

// ─── SQL Azure AD Administrator ──────────────────────────────────────────────
// Sets you as the AAD admin so you can connect via AAD and run the post-deploy
// T-SQL that registers the App Service managed identity as a database user.
// Set manually after first deploy if this resource fails:
//   az sql server ad-admin create \
//     --resource-group heavyuse-rg \
//     --server heavyuse-sql \
//     --display-name <your-email> \
//     --object-id <your-aad-object-id>
resource sqlAadAdmin 'Microsoft.Sql/servers/administrators@2023-05-01-preview' = if (aadAdminObjectId != '') {
  parent: sqlServer
  name: 'ActiveDirectory'
  properties: {
    administratorType: 'ActiveDirectory'
    login: aadAdminLogin
    sid: aadAdminObjectId
    tenantId: tenant().tenantId
  }
}

// Disables SQL password auth entirely — only AAD/managed identity connections are accepted.
// Requires sqlAadAdmin to be set first; deploying this before the AAD admin locks you out.
resource sqlAadOnlyAuth 'Microsoft.Sql/servers/azureADOnlyAuthentications@2023-05-01-preview' = if (aadAdminObjectId != '') {
  parent: sqlServer
  name: 'Default'
  dependsOn: [sqlAadAdmin]
  properties: {
    azureADOnlyAuthentication: true
  }
}

// ─── VNet + Subnet ───────────────────────────────────────────────────────────
// Regional VNet integration routes App Service egress through a delegated subnet.
// The SQL service endpoint on that subnet lets us use a VNet rule instead of
// the broad "allow all Azure services" firewall rule (0.0.0.0/0.0.0.0).
resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: '${appName}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        name: 'app-subnet'
        properties: {
          addressPrefix: '10.0.1.0/24'
          delegations: [
            {
              name: 'app-service'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
          serviceEndpoints: [
            {
              service: 'Microsoft.Sql'
              locations: [location]
            }
          ]
        }
      }
    ]
  }
}

resource vnetIntegration 'Microsoft.Web/sites/networkConfig@2023-01-01' = {
  parent: app
  name: 'virtualNetwork'
  properties: {
    subnetResourceId: vnet.properties.subnets[0].id
    swiftSupported: true
  }
}

// ─── SQL Firewall Rules ───────────────────────────────────────────────────────
// App Service reaches SQL via the VNet rule below — no broad Azure rule needed.
// Only your developer IP and the app subnet are permitted.
resource sqlVnetRule 'Microsoft.Sql/servers/virtualNetworkRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AppServiceVnet'
  properties: {
    virtualNetworkSubnetId: vnet.properties.subnets[0].id
    ignoreMissingVnetServiceEndpoint: false
  }
}

resource fwDeveloper 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = if (developerIp != '') {
  parent: sqlServer
  name: 'DeveloperAccess'
  properties: {
    startIpAddress: developerIp
    endIpAddress: developerIp
  }
}

// ─── Key Vault ────────────────────────────────────────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${appName}-kv'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource kvSecrets 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = [for item in nonEmptySecrets: {
  parent: keyVault
  name: toLower(replace(item.key, '_', '-'))
  properties: {
    value: item.value
  }
}]

// Grants the App Service managed identity read access to Key Vault secrets
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, app.id, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grants the deploying user full secrets management access in the portal
var kvSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
resource kvAdminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, aadAdminObjectId, kvSecretsOfficerRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsOfficerRoleId)
    principalId: aadAdminObjectId
    principalType: 'User'
  }
}

// ─── Storage Account (media files) ───────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${appName}media'
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource mediaContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/media'
  properties: {
    publicAccess: 'Blob'
  }
}

var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, app.id, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Log Analytics + Application Insights ────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${appName}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────────────
output appUrl string = 'https://${app.properties.defaultHostName}'
output appPrincipalId string = app.identity.principalId
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDbBasic.name
output storageAccountName string = storageAccount.name
output mediaUrl string = '${storageAccount.properties.primaryEndpoints.blob}media/'
