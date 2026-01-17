#!/bin/sh
set -e

# Set default value for LOG_GROUP_NAME if not provided
LOG_GROUP_NAME=${LOG_GROUP_NAME:-/app/logs}

# Replace LOG_GROUP_NAME environment variable in the config file
sed "s|\${LOG_GROUP_NAME}|${LOG_GROUP_NAME}|g" \
    /opt/aws/amazon-cloudwatch-agent/bin/config.template.json > /opt/aws/amazon-cloudwatch-agent/bin/default_linux_config.json

echo "CloudWatch Agent starting with LOG_GROUP_NAME=${LOG_GROUP_NAME}"

# Start the CloudWatch Agent
exec /opt/aws/amazon-cloudwatch-agent/bin/start-amazon-cloudwatch-agent
