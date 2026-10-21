param location string = 'eastus2'
param namePrefix string = 'football-courtroom'
param imageTag string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: 'fccr${uniqueString(resourceGroup().id)}'
}
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: '${namePrefix}-pull'
}
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: '${namePrefix}-env'
}
resource frontend 'Microsoft.Web/staticSites@2023-12-01' existing = {
  name: '${namePrefix}-web'
}

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
        traffic: [{ latestRevision: true, weight: 100 }]
      }
    }
    template: {
      containers: [{
        name: 'backend'
        image: '${registry.properties.loginServer}/football-courtroom:${imageTag}'
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        env: [
          { name: 'FOOTBALL_PUBLIC_MODE', value: 'true' }
          { name: 'FOUNDRY_LIVE_ENABLED', value: 'false' }
          { name: 'COURTROOM_LIVE_ENABLED', value: 'false' }
          { name: 'CORS_ORIGINS', value: 'https://${frontend.properties.defaultHostname}' }
        ]
        probes: [
          {
            type: 'Startup'
            httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 24
          }
          {
            type: 'Readiness'
            httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
          }
          {
            type: 'Liveness'
            httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
            periodSeconds: 20
            timeoutSeconds: 2
            failureThreshold: 3
          }
        ]
      }]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

output backendUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output frontendUrl string = 'https://${frontend.properties.defaultHostname}'
