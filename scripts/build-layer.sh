#!/bin/bash

# Build script for Lambda layer dependencies
set -e

echo "Building Lambda layer dependencies..."

# Create temporary directory
TEMP_DIR=$(mktemp -d)
LAYER_DIR="lambda/layers/shared"

# Install dependencies
pip install -r ${LAYER_DIR}/requirements.txt -t ${TEMP_DIR}

# Copy to layer directory
mkdir -p ${LAYER_DIR}/python/lib/python3.12/site-packages
cp -r ${TEMP_DIR}/* ${LAYER_DIR}/python/lib/python3.12/site-packages/

# Clean up
rm -rf ${TEMP_DIR}

echo "Lambda layer dependencies built successfully!"