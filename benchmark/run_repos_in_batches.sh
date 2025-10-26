#!/bin/bash
set -e  # stop on error

# Configuration
BATCH_SIZE=8
RUBRIC_DIR="rubrics/manual"

# Find all .json files and strip the extension to get repo names
repos=($(basename -s .json $(ls "$RUBRIC_DIR"/*.json)))

echo "============================================================"
echo "=== 🚀 Batch Repository Runner"
echo "=== Total repos: ${#repos[@]}"
echo "=== Batch size: $BATCH_SIZE"
echo "=== Time: $(date)"
echo "============================================================"
echo

# Function to wait for all running screens to finish
wait_for_batch_completion() {
    local batch_repos=("$@")
    local batch_size=${#batch_repos[@]}
    echo "⏳ Waiting for batch to complete..."
    
    while true; do
        local running_count=0
        
        for repo in "${batch_repos[@]}"; do
            if screen -list | grep -q "[.]$repo"; then
                ((running_count++))
            fi
        done
        
        if [[ $running_count -eq 0 ]]; then
            echo "✅ All repositories in batch completed!"
            break
        fi
        
        echo "   Still running: $running_count/$batch_size repositories..."
        sleep 30  # Check every 30 seconds
    done
}

# Function to cleanup Docker resources
cleanup_docker() {
    echo "🧹 Cleaning up Docker resources..."
    echo "   Pruning system, containers, images, and volumes..."
    
    if docker system prune -a --volumes -f; then
        echo "✅ Docker cleanup completed successfully"
    else
        echo "⚠️  Docker cleanup encountered some issues, but continuing..."
    fi
    
    echo "   Current Docker disk usage:"
    docker system df
    echo
}

# Process repositories in batches
batch_num=1
total_batches=$(( (${#repos[@]} + BATCH_SIZE - 1) / BATCH_SIZE ))

for ((i=0; i<${#repos[@]}; i+=BATCH_SIZE)); do
    echo "============================================================"
    echo "=== 📦 Starting Batch $batch_num/$total_batches"
    echo "============================================================"
    
    # Get the current batch of repos
    batch_repos=("${repos[@]:$i:$BATCH_SIZE}")
    
    echo "Repositories in this batch:"
    printf '  - %s\n' "${batch_repos[@]}"
    echo
    
    # Launch screens for this batch
    for repo in "${batch_repos[@]}"; do
        echo "Starting screen for $repo..."
        screen -dmS "$repo" bash -c "python3 batch_evaluate.py \
            --skip-warnings --verbose \
            --rubric-dir '$RUBRIC_DIR' \
            --repo '$repo'"
        echo "  → Screen '$repo' started."
    done
    
    echo
    echo "🏃 All screens for batch $batch_num launched!"
    echo "Use 'screen -ls' to see running screens."
    echo
    
    # Wait for this batch to complete
    wait_for_batch_completion "${batch_repos[@]}"
    
    # Cleanup Docker resources between batches (except for the last batch)
    if [[ $batch_num -lt $total_batches ]]; then
        cleanup_docker
        echo "💤 Waiting 10 seconds before starting next batch..."
        sleep 10
    fi
    
    ((batch_num++))
    echo
done

echo "============================================================"
echo "=== 🎉 ALL BATCHES COMPLETED!"
echo "=== Total repositories processed: ${#repos[@]}"
echo "=== Total batches: $total_batches"
echo "=== Completion time: $(date)"
echo "============================================================"

# Final Docker cleanup
echo
echo "🧹 Performing final Docker cleanup..."
cleanup_docker

echo "✨ All done! Check the reports in 'reports-by-repo/' and 'reports-by-model/' directories."