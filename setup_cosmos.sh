#!/bin/bash

# Setup script for Cosmos DB conversation storage

# Configuration
COSMOS_ACCOUNT_NAME="yoast-conversation-history"
RESOURCE_GROUP="yoast"  # Update this to your resource group name
WEB_APP_NAME="nlw"  # Update this to your web app name
DATABASE_NAME="nlweb"
CONTAINER_NAME="conversations"
PARTITION_KEY="/conversation_id"

echo "Setting up Cosmos DB for conversation storage..."

# Step 1: Get the web app's managed identity principal ID
echo "Getting web app managed identity..."
PRINCIPAL_ID=$(az webapp identity show \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query principalId \
    --output tsv)

if [ -z "$PRINCIPAL_ID" ]; then
    echo "Error: Could not get managed identity. Make sure the web app has system-assigned managed identity enabled."
    exit 1
fi

echo "Web app managed identity principal ID: $PRINCIPAL_ID"

# Step 2: Assign Cosmos DB Built-in Data Contributor role
echo "Assigning Cosmos DB Built-in Data Contributor role..."
COSMOS_RESOURCE_ID=$(az cosmosdb show \
    --name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query id \
    --output tsv)

# Cosmos DB Built-in Data Contributor role ID
ROLE_DEFINITION_ID="00000000-0000-0000-0000-000000000002"

az cosmosdb sql role assignment create \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --scope "$COSMOS_RESOURCE_ID" \
    --principal-id $PRINCIPAL_ID \
    --role-definition-id $ROLE_DEFINITION_ID

echo "Role assignment complete."

# Step 3: Create database
echo "Creating database '$DATABASE_NAME'..."
az cosmosdb sql database create \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --name $DATABASE_NAME \
    || echo "Database may already exist, continuing..."

# Step 4: Create container with partition key
echo "Creating container '$CONTAINER_NAME' with partition key '$PARTITION_KEY'..."
az cosmosdb sql container create \
    --account-name $COSMOS_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --database-name $DATABASE_NAME \
    --name $CONTAINER_NAME \
    --partition-key-path $PARTITION_KEY \
    --throughput 400 \
    || echo "Container may already exist, continuing..."

echo ""
echo "Setup complete!"
echo "Database: $DATABASE_NAME"
echo "Container: $CONTAINER_NAME"
echo "Partition key: $PARTITION_KEY"
echo ""
echo "Next steps:"
echo "1. Set the environment variable in your web app:"
echo "   az webapp config appsettings set --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP --settings AZURE_COSMOS_ENDPOINT=https://$COSMOS_ACCOUNT_NAME.documents.azure.com:443/"
echo "2. Restart the web app:"
echo "   az webapp restart --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
