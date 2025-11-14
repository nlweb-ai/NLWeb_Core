#!/bin/bash

# Azure Web App deployment script for NLWeb_Core

# Configuration
WEBAPP_NAME="nlw"
RESOURCE_GROUP="yoast"
VECTOR_DB_NAME="yoast-vector-db"
VECTOR_DB_ENDPOINT="https://yoast-vector-db.search.windows.net"

# Generate zip file name with app name and timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ZIP_FILE="${WEBAPP_NAME}_deploy_${TIMESTAMP}.zip"

echo "========================================="
echo "Azure Web App Deployment Script"
echo "========================================="
echo "Web App: $WEBAPP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Vector DB: $VECTOR_DB_NAME"
echo "Vector DB Endpoint: $VECTOR_DB_ENDPOINT"
echo ""

# Remove old zip if exists
echo "Removing old deployment zip..."
rm -f ${WEBAPP_NAME}_deploy_*.zip

# Create deployment zip
echo "Creating deployment zip file..."
zip -r $ZIP_FILE . \
  -x "*.git*" \
  -x "*.zip" \
  -x "node_modules/*" \
  -x "docs/*" \
  -x "*__pycache__/*" \
  -x "*.DS_Store*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.pyd" \
  -x ".Python" \
  -x "env/*" \
  -x "venv/*" \
  -x ".venv/*" \
  -x ".claude/*" \
  -x "*.egg-info/*" \
  -x "dist/*" \
  -x "build/*" \
  -x ".pytest_cache/*" \
  -x ".mypy_cache/*" \
  -x "*.log" \
  -x "examples/*" \
  -x "*.md"

# Show zip file size
echo ""
echo "Deployment zip created: $ZIP_FILE"
ls -lh $ZIP_FILE

# Deploy to Azure
echo ""
echo "Deploying to Azure Web App..."
echo ""

az webapp deploy \
  --resource-group $RESOURCE_GROUP \
  --name $WEBAPP_NAME \
  --src-path $ZIP_FILE \
  --type zip

if [ $? -ne 0 ]; then
    echo ""
    echo "Deployment failed. Check the error messages above."
    exit 1
fi

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

# Assign Search Index Data Reader role to the managed identity for the vector database
echo ""
echo "Assigning Search Index Data Reader role to managed identity..."

# Get the search service resource ID
SEARCH_RESOURCE_ID=$(az search service show \
  --name $VECTOR_DB_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id \
  --output tsv)

if [ -z "$SEARCH_RESOURCE_ID" ]; then
    echo "Failed to get search service resource ID"
    exit 1
fi

# Assign the role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Reader" \
  --scope $SEARCH_RESOURCE_ID

# Also assign Search Index Data Contributor for write access if needed
echo ""
echo "Assigning Search Index Data Contributor role to managed identity..."
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Search Index Data Contributor" \
  --scope $SEARCH_RESOURCE_ID

# Configure startup command
echo ""
echo "Configuring startup command..."
az webapp config set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"

# Configure app settings for the web app
echo ""
echo "Configuring app settings..."
az webapp config appsettings set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    VECTOR_DB_ENDPOINT="$VECTOR_DB_ENDPOINT" \
    AZURE_SEARCH_ENDPOINT="$VECTOR_DB_ENDPOINT" \
    AZURE_SEARCH_USE_MANAGED_IDENTITY="true" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

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
echo "App Settings configured:"
echo "  - VECTOR_DB_ENDPOINT: $VECTOR_DB_ENDPOINT"
echo "  - AZURE_SEARCH_ENDPOINT: $VECTOR_DB_ENDPOINT"
echo "  - AZURE_SEARCH_USE_MANAGED_IDENTITY: true"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "To test the /ask endpoint:"
echo "  curl 'https://${WEBAPP_NAME}.azurewebsites.net/ask?query=test'"
