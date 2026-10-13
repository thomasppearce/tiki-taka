// Tiki-Taka hosting: where the app runs, next to the agent resources in main.bicep.
//
// - The backend (FastAPI) on Azure Container Apps, Consumption: it scales to zero when nobody is
//   watching and boots in seconds on the next visit (the matchday is baked into the image). One
//   replica at most, because the matchday clock and the channel live in its memory.
// - Two scheduled Container Apps jobs keep it warm through judging: one sets `minReplicas` to 1
//   when judging starts, the other back to 0 when it ends. A replica held by `minReplicas` is
//   billed at the idle rate (about $0.78 a day); one held by a scale rule would be billed active.
// - Its image in Azure Container Registry (Basic), pulled with a managed identity: no secrets.
// - That identity may use the Foundry project and models (the agents) and read the AI Search
//   knowledge base.
// - The frontend (a Next.js static export) on Azure Static Web Apps, Free.
// - Logs in Log Analytics, and Application Insights for the agents' traces, connected to the
//   Foundry project so the traces show in Foundry.
//
// Deploy: see infra/README.md. Resource shapes from Microsoft Learn's template reference
// (2026-10-12): Microsoft.App 2026-07-01, Microsoft.Web/staticSites 2024-11-01,
// Microsoft.ContainerRegistry 2025-11-01; API versions checked with `az provider show`.

targetScope = 'resourceGroup'

@description('Region for the backend and its resources (the agents are in the same region).')
param location string = resourceGroup().location

@description('Static Web Apps is not offered in every region; Central US is the nearest.')
param webLocation string = 'centralus'

@description('The name main.bicep used, to find the Foundry resource and the search service.')
param name string = 'matchdesk'

@description('Short name for the hosting resources.')
param app string = 'tikitaka'

@description('The backend image. The first deployment runs a placeholder until an image is built.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('0 scales to zero when idle; 1 keeps one replica warm. The jobs below switch it.')
@allowed([0, 1])
param minReplicas int = 0

// Container Apps jobs read cron in UTC. Judging runs Oct 27 to Nov 10, 11:59 PM Pacific: warm
// from midnight Pacific on Oct 27 (07:00 UTC, daylight time) to 2 AM Pacific on Nov 11 (10:00
// UTC, standard time). The schedules repeat yearly; take the jobs down with the rest after.
@description('When the backend starts staying warm (UTC cron).')
param warmFrom string = '0 7 27 10 *'

@description('When it goes back to scaling to zero (UTC cron).')
param warmUntil string = '0 10 11 11 *'

var suffix = uniqueString(resourceGroup().id)
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  contributor: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // formerly "Azure AI User"
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
}

resource foundry 'Microsoft.CognitiveServices/accounts@2026-07-01' existing = {
  name: '${name}-${suffix}'
}

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: '${name}-search-${suffix}'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2026-03-01' = {
  name: '${app}-logs-${suffix}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${app}-insights-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-07-01' existing = {
  parent: foundry
  name: name
}

// Connecting App Insights to the Foundry project is what puts the agents' traces in Foundry
// (Observability > Traces); locally, the backend reads the connection string from here too.
resource tracing 'Microsoft.CognitiveServices/accounts/projects/connections@2026-07-01' = {
  parent: project
  name: insights.name
  properties: {
    category: 'AppInsights'
    target: insights.id
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: insights.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: insights.id
    }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: '${app}${suffix}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: '${app}-backend'
  location: location
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, identity.id, roles.acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource agentsUseFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, identity.id, roles.foundryUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource agentsUseModels 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, identity.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource agentsReadKnowledge 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, identity.id, roles.searchIndexDataReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataReader)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource environment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: '${app}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource web 'Microsoft.Web/staticSites@2024-11-01' = {
  name: '${app}-web'
  location: webLocation
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

var fromRegistry = startsWith(backendImage, registry.properties.loginServer)

resource backend 'Microsoft.App/containerApps@2026-07-01' = {
  name: '${app}-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: fromRegistry ? 8000 : 80
        transport: 'auto'
        allowInsecure: false
      }
      registries: fromRegistry
        ? [
            {
              server: registry.properties.loginServer
              identity: identity.id
            }
          ]
        : []
      secrets: [
        {
          name: 'appinsights'
          value: insights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: backendImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${name}' }
            { name: 'FOUNDRY_MODEL', value: 'agents' }
            { name: 'FOUNDRY_MODEL_LABEL', value: 'gpt-5.4-mini' }
            { name: 'FOUNDRY_WATCHER_MODEL', value: 'agents-luna' }
            { name: 'FOUNDRY_EMBEDDING_MODEL', value: 'embeddings' }
            { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'ALLOWED_ORIGINS', value: 'https://${web.properties.defaultHostname}' }
            { name: 'MATCH_START_MINUTE', value: '55' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 1 // the matchday clock and the channel live in this replica's memory
        cooldownPeriod: 600 // stay up ten minutes after the last viewer, then sleep
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [pull]
}

// The warm/cold switch: `make warm` and `make cold` on a timer, under an identity that may change
// the backend app and nothing else.
resource scheduler 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: '${app}-scheduler'
  location: location
}

resource schedulerScalesBackend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: backend
  name: guid(backend.id, scheduler.id, roles.contributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.contributor)
    principalId: scheduler.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

var switches = [
  { name: 'warm', cron: warmFrom, minReplicas: 1 }
  { name: 'cold', cron: warmUntil, minReplicas: 0 }
]

resource switchJobs 'Microsoft.App/jobs@2026-07-01' = [
  for s in switches: {
    name: '${app}-${s.name}'
    location: location
    identity: {
      type: 'UserAssigned'
      userAssignedIdentities: {
        '${scheduler.id}': {}
      }
    }
    properties: {
      environmentId: environment.id
      workloadProfileName: 'Consumption'
      configuration: {
        triggerType: 'Schedule'
        scheduleTriggerConfig: {
          cronExpression: s.cron
          parallelism: 1
          replicaCompletionCount: 1
        }
        replicaTimeout: 600
        replicaRetryLimit: 2
      }
      template: {
        containers: [
          {
            name: 'switch'
            image: 'mcr.microsoft.com/azure-cli:2.90.0'
            command: ['/bin/sh', '-c']
            args: [
              'az login --identity --client-id "$AZURE_CLIENT_ID" --allow-no-subscriptions --output none && az containerapp update --ids "$APP_ID" --min-replicas ${s.minReplicas} --query properties.template.scale --output json'
            ]
            env: [
              { name: 'AZURE_CLIENT_ID', value: scheduler.properties.clientId }
              { name: 'APP_ID', value: backend.id }
            ]
            resources: {
              cpu: json('0.5')
              memory: '1Gi'
            }
          }
        ]
      }
    }
    dependsOn: [schedulerScalesBackend]
  }
]

output apiUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output webUrl string = 'https://${web.properties.defaultHostname}'
output webName string = web.name
output apiName string = backend.name
output registryName string = registry.name
output registryServer string = registry.properties.loginServer
