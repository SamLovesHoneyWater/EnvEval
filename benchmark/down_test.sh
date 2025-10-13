#!/bin/bash

# Clone Dockerfiles to be evaluated
git clone https://github.com/EaminC/ENVGYM-baseline.git

# Dataset list generated from Excel file
repos=(
"Fairify|https://github.com/sumonbis/Fairify.git"
"facebook_zstd|https://github.com/facebook/zstd"
)

# Create data directory if it doesn't exist
mkdir -p ./data

# Clone function
for entry in "${repos[@]}"; do
  name=$(echo "$entry" | cut -d '|' -f 1)
  url=$(echo "$entry" | cut -d '|' -f 2)

  if [ -d "./data/$name" ]; then
    echo "[SKIP] $name already exists"
  else
    echo "[CLONE] $name ..."
    git clone "$url" "./data/$name"
  fi
done

echo "All datasets downloaded successfully!"
