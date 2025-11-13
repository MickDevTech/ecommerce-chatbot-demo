#!/bin/bash
# Script to regenerate package-lock.json on linux x64 using Docker

echo "🔄 Regenerating package-lock.json for linux x64..."

# Remove old package-lock.json and node_modules
echo "📦 Cleaning old files..."
rm -f package-lock.json
rm -rf node_modules

# Run npm install in a linux/amd64 Docker container
echo "🐳 Running npm install in Docker (linux/amd64)..."
docker run --rm \
  --platform linux/amd64 \
  -v "$(pwd):/app" \
  -w /app \
  node:18-alpine \
  npm install

echo "✅ Done! New package-lock.json generated for linux x64"
echo "📝 Please commit the new package-lock.json to your repository"
