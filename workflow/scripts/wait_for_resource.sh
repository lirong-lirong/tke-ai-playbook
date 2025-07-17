#!/bin/sh
set -eu

# This script is executed by the wait-resource-operator workflow template.
# It reads parameters as environment variables.

# Initialize status file
echo "false" > /tmp/status_code

# Skip if the previous step failed
if [ "$PRE_STATUS" = "false" ]; then
  echo "Skipping wait due to previous step failure (PRE_STATUS=false)."
  # Exit successfully to allow the workflow to continue to cleanup
  exit 0
fi

# Set timeout
END_TIME=$(( $(date +%s) + TIMEOUT ))

echo "Waiting for resource type '$RESOURCE_TYPE' named '$RESOURCE_NAME' in namespace '$NAMESPACE' (timeout: ${TIMEOUT}s)..."

# Resource type handling
case "$RESOURCE_TYPE" in
  statefulset)
    echo "Waiting for StatefulSet $RESOURCE_NAME to be ready..."
    if kubectl rollout status "statefulset/$RESOURCE_NAME" -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
      # Check for the corresponding Service
      SERVICE_NAME=$(kubectl get svc -l app.kubernetes.io/instance="$RESOURCE_NAME" -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
      if [ -n "$SERVICE_NAME" ]; then
        echo "StatefulSet and its Service '$SERVICE_NAME' are ready."
        echo "true" > /tmp/status_code
      else
        echo "Error: StatefulSet is ready, but its corresponding Service was not found."
      fi
    else
      echo "Error: Timeout waiting for StatefulSet $RESOURCE_NAME to become ready."
    fi
    ;;
    
  job)
    echo "Monitoring Job $RESOURCE_NAME..."
    job_completed="false"
    
    while [ "$(date +%s)" -lt "$END_TIME" ]; do
      # Fetch the status conditions for "Complete" and "Failed"
      job_status_complete=$(kubectl get job "$RESOURCE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || true)
      job_status_failed=$(kubectl get job "$RESOURCE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)
      
      if [ "$job_status_complete" = "True" ]; then
        job_completed="success"
        break
      elif [ "$job_status_failed" = "True" ]; then
        job_completed="failed"
        break
      fi
      
      sleep 5
    done
    
    # Process the final result
    if [ "$job_completed" = "success" ]; then
      echo "Job $RESOURCE_NAME completed successfully."
      echo "true" > /tmp/status_code
    elif [ "$job_completed" = "failed" ]; then
      echo "Error: Job $RESOURCE_NAME failed."
    else
      echo "Error: Job $RESOURCE_NAME did not complete within the timeout period."
    fi
    ;;
    
  *)
    echo "Error: Unsupported resource type: $RESOURCE_TYPE"
    ;;
esac

# Final check
if [ "$(cat /tmp/status_code)" = "true" ]; then
  echo "Resource wait successful."
else
  echo "Resource wait failed."
fi
