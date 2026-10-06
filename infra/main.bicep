// Match Desk: the Azure resources the agent team runs on.
//
// - A Microsoft Foundry resource (AIServices) with one project, where the agents, tracing, and
//   evaluations live, plus two model deployments: one for the agents, one for embeddings.
// - Azure AI Search (Free tier), which holds the knowledge base (Foundry IQ) the Explainer
//   retrieves club tactics and the laws of the game from.
// - Role assignments so the developer (and later the backend's managed identity) can use both
//   with Microsoft Entra ID. Local (key) auth is disabled on Foundry: no keys to leak.
//
// Deploy: see infra/README.md. Resource shapes follow Microsoft Learn (2026-10-06):
// https://learn.microsoft.com/en-us/azure/foundry/how-to/create-projects
// https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/projects
// https://learn.microsoft.com/en-us/azure/templates/microsoft.search/searchservices

targetScope = 'resourceGroup'

@description('Region for every resource. North Central US offers the models, quota, and AI Search Free with agentic retrieval.')
param location string = resourceGroup().location

@description('Short name used to build resource names.')
param name string = 'matchdesk'

@description('Object ID of the developer (az ad signed-in-user show --query id -o tsv), granted access to Foundry and AI Search.')
param developerPrincipalId string

@description('The model the agents use, and how it is deployed. Swap for gpt-6-luna once quota allows.')
param agentModel object = {
  name: 'gpt-5.4-mini'
  version: '2026-03-17'
  sku: 'DataZoneStandard'
  capacity: 100 // thousands of tokens per minute
}

@description('The embedding model for the knowledge base.')
param embeddingModel object = {
  name: 'text-embedding-3-small'
  version: '1'
  sku: 'GlobalStandard'
  capacity: 100
}

var suffix = uniqueString(resourceGroup().id)

// Built-in role definition IDs (looked up with `az role definition list`, 2026-10-06).
var roles = {
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // formerly "Azure AI User"
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource foundry 'Microsoft.CognitiveServices/accounts@2026-07-01' = {
  name: '${name}-${suffix}'
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned' // project management requires a managed identity
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: '${name}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-07-01' = {
  parent: foundry
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Match Desk'
    description: 'The agent team behind the Match Desk broadcast control room.'
  }
}

resource agentDeployment 'Microsoft.CognitiveServices/accounts/deployments@2026-07-01' = {
  parent: foundry
  name: 'agents'
  sku: {
    name: agentModel.sku
    capacity: agentModel.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: agentModel.name
      version: agentModel.version
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [project] // one operation at a time on the account: project first, then models
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2026-07-01' = {
  parent: foundry
  name: 'embeddings'
  sku: {
    name: embeddingModel.sku
    capacity: embeddingModel.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModel.name
      version: embeddingModel.version
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [agentDeployment] // deployments on one account must be created one at a time
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: '${name}-search-${suffix}'
  location: location
  sku: {
    name: 'free'
  }
  identity: {
    type: 'SystemAssigned' // used to call the embedding model when vectorizing
  }
  properties: {
    hostingMode: 'Default'
    partitionCount: 1
    replicaCount: 1
    publicNetworkAccess: 'enabled'
    semanticSearch: 'free'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// The developer: use the project and its models, and manage the knowledge base.
resource developerFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, developerPrincipalId, roles.foundryUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
    principalId: developerPrincipalId
    principalType: 'User'
  }
}

resource developerSearchData 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, developerPrincipalId, roles.searchIndexDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
    principalId: developerPrincipalId
    principalType: 'User'
  }
}

resource developerSearchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, developerPrincipalId, roles.searchServiceContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
    principalId: developerPrincipalId
    principalType: 'User'
  }
}

// AI Search calls the embedding deployment to vectorize knowledge and queries.
resource searchUsesEmbeddings 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, search.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output foundryName string = foundry.name
output projectName string = project.name
output projectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output openAiEndpoint string = 'https://${foundry.properties.customSubDomainName}.openai.azure.com/'
output agentDeploymentName string = agentDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
