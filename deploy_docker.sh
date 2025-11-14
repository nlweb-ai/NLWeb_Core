#!/bin/bash

# Azure Web App deployment script for NLWeb_Core using Docker

# Configuration
WEBAPP_NAME="nlw"
RESOURCE_GROUP="yoast"
VECTOR_DB_NAME="yoast-vector-db"
VECTOR_DB_ENDPOINT="https://yoast-vector-db.search.windows.net"
REGISTRY_NAME="yoastcontainerregistry"  # Azure Container Registry name
IMAGE_NAME="nlweb-core"
IMAGE_TAG="latest"

echo "========================================="
echo "Azure Web App Docker Deployment"
echo "========================================="
echo "Web App: $WEBAPP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Vector DB: $VECTOR_DB_NAME"
echo "Registry: $REGISTRY_NAME"
echo ""

# Build Docker image using Azure Container Registry (ACR Build)
echo "Building Docker image in Azure Container Registry..."
az acr build \
  --registry $REGISTRY_NAME \
  --image $IMAGE_NAME:$IMAGE_TAG \
  --file Dockerfile \
  .

if [ $? -ne 0 ]; then
    echo "ACR build failed"
    exit 1
fi

# Configure Web App to use Docker container
echo ""
echo "Configuring Web App to use Docker container..."
az webapp config container set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG \
  --docker-registry-server-url https://$REGISTRY_NAME.azurecr.io

# Enable system-assigned managed identity
echo ""
echo "Enabling system-assigned managed identity..."
az webapp identity assign \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP

# Get the managed identity principal ID
echo ""
echo "Getting managed identity principal ID..."
PRINCIPAL_ID=$(az webapp identity show \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId \
  --output tsv)

if [ -z "$PRINCIPAL_ID" ]; then
    echo "Failed to get managed identity principal ID"
    exit 1
fi

echo "Managed Identity Principal ID: $PRINCIPAL_ID"

# Get the search service resource ID
echo ""
echo "Getting search service resource ID..."
SEARCH_RESOURCE_ID=$(az search service show \
  --name $VECTOR_DB_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id \
  --output tsv)

if [ -z "$SEARCH_RESOURCE_ID" ]; then
    echo "Failed to get search service resource ID"
    exit 1
fi

# Assign Search Index Data Reader role
echo ""
echo "Assigning Search Index Data Reader role..."
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Reader" \
  --scope $SEARCH_RESOURCE_ID

# Assign Search Index Data Contributor role
echo ""
echo "Assigning Search Index Data Contributor role..."
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Contributor" \
  --scope $SEARCH_RESOURCE_ID

# Configure app settings
echo ""
echo "Configuring app settings..."
az webapp config appsettings set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    VECTOR_DB_ENDPOINT="$VECTOR_DB_ENDPOINT" \
    AZURE_SEARCH_ENDPOINT="$VECTOR_DB_ENDPOINT" \
    AZURE_SEARCH_USE_MANAGED_IDENTITY="true" \
    WEBSITES_PORT="8000"

# Restart the web app
echo ""
echo "Restarting web app..."
az webapp restart --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP

echo ""
echo "========================================="
echo "Deployment Successful!"
echo "========================================="
echo "Web App URL: https://${WEBAPP_NAME}.azurewebsites.net"
echo ""
echo "Managed Identity has been enabled and assigned roles:"
echo "  - Search Index Data Reader"
echo "  - Search Index Data Contributor"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "To test the /ask endpoint:"
echo "  curl 'https://${WEBAPP_NAME}.azurewebsites.net/health'"
