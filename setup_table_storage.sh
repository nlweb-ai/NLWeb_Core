#!/bin/bash

# Setup script for Azure Table Storage conversation storage

# Configuration
STORAGE_ACCOUNT_NAME="yoaststorage"  # Update if needed
RESOURCE_GROUP="yoast"
TABLE_NAME="conversations"

echo "Setting up Azure Table Storage for conversation storage..."

# Check if storage account exists
echo "Checking if storage account '$STORAGE_ACCOUNT_NAME' exists..."
ACCOUNT_EXISTS=$(az storage account show \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "name" \
    --output tsv 2>/dev/null)

if [ -z "$ACCOUNT_EXISTS" ]; then
    echo "Storage account does not exist. Creating..."
    az storage account create \
        --name $STORAGE_ACCOUNT_NAME \
        --resource-group $RESOURCE_GROUP \
        --location westus2 \
        --sku Standard_LRS \
        --kind StorageV2

    echo "Storage account created."
else
    echo "Storage account already exists."
fi

# Get connection string
echo "Retrieving connection string..."
CONNECTION_STRING=$(az storage account show-connection-string \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "connectionString" \
    --output tsv)

if [ -z "$CONNECTION_STRING" ]; then
    echo "Error: Could not retrieve connection string"
    exit 1
fi

echo "Connection string retrieved."

# Create table
echo "Creating table '$TABLE_NAME'..."
az storage table create \
    --name $TABLE_NAME \
    --connection-string "$CONNECTION_STRING" \
    || echo "Table may already exist, continuing..."

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update set_keys.sh with the connection string:"
echo "   export AZURE_STORAGE_CONNECTION_STRING=\"$CONNECTION_STRING\""
echo ""
echo "2. Source the file:"
echo "   source set_keys.sh"
echo ""
echo "Or for Azure Web App, set the environment variable:"
echo "   az webapp config appsettings set \\"
echo "     --name nlw \\"
echo "     --resource-group yoast \\"
echo "     --settings AZURE_STORAGE_CONNECTION_STRING=\"$CONNECTION_STRING\""
echo ""
echo "Table Storage costs: ~$0.045/GB/month + $0.00036 per 10,000 transactions"
echo "(Approximately 100x cheaper than Cosmos DB for this use case)"
