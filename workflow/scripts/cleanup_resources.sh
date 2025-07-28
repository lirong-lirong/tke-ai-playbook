#!/bin/sh
# This script is executed by the cleanup-operator workflow template.
# It reads parameters as environment variables.

echo "Starting cleanup for release: $RELEASE_NAME in namespace $NAMESPACE"
echo "Cleanup strategy: $CLEANUP_STRATEGY"
echo "Delete PVCs: $DELETE_PVCS"

# Standard cleanup: delete Helm release
if [ "$CLEANUP_STRATEGY" != "minimal" ]; then
  echo "Uninstalling Helm releases..."
  helm uninstall "$RELEASE_NAME" -n "$NAMESPACE" || echo "Helm uninstall for $RELEASE_NAME failed, continuing..."
  helm uninstall "${RELEASE_NAME}-test" -n "$NAMESPACE" || echo "Helm uninstall for ${RELEASE_NAME}-test failed, continuing..."
fi

# Aggressive cleanup: force delete all related resources
if [ "$CLEANUP_STRATEGY" = "aggressive" ]; then
  echo "Force deleting all related resources..."
  
  # 删除所有相关资源
  kubectl delete all -l app.kubernetes.io/instance=$RELEASE_NAME -n $NAMESPACE --force --grace-period=0 --timeout=60s || true
  kubectl delete all -l app.kubernetes.io/instance=${RELEASE_NAME}-test -n $NAMESPACE --force --grace-period=0 --timeout=60s || true
  
  kubectl delete crd -l app.kubernetes.io/instance="$RELEASE_NAME" -n "$NAMESPACE" || echo "kubectl delete crd for $RELEASE_NAME failed, continuing..."
  
  if [ "$DELETE_PVCS" = "true" ]; then
    echo "Deleting PVCs..."
    kubectl delete pvc -l app.kubernetes.io/instance="$RELEASE_NAME" -n "$NAMESPACE" || echo "kubectl delete pvc for $RELEASE_NAME failed, continuing..."
    kubectl delete pvc -l app.kubernetes.io/instance="${RELEASE_NAME}-test" -n "$NAMESPACE" || echo "kubectl delete pvc for ${RELEASE_NAME}-test failed, continuing..."
  fi
fi

# Minimal cleanup: only delete Pods (for quick restart)
if [ "$CLEANUP_STRATEGY" = "minimal" ]; then
  echo "Deleting pods only..."
  kubectl delete pods -l app.kubernetes.io/instance="$RELEASE_NAME" -n "$NAMESPACE" --force --grace-period=0 || echo "kubectl delete pods for $RELEASE_NAME failed, continuing..."
  kubectl delete pods -l app.kubernetes.io/instance="${RELEASE_NAME}-test" -n "$NAMESPACE" --force --grace-period=0 || echo "kubectl delete pods for ${RELEASE_NAME}-test failed, continuing..."
fi

echo "Cleanup completed for $RELEASE_NAME"
