FROM alpine:3.23.2 AS builder

# Copy entrypoint and make it executable
COPY ./entrypoint.sh /tmp/entrypoint.sh
RUN chmod +x /tmp/entrypoint.sh

# Final stage
FROM amazon/cloudwatch-agent:1.300062.0b1304

# Copy shell, core utils, and libraries from Alpine
COPY --from=builder /bin/sh /bin/sh
COPY --from=builder /bin/sed /bin/sed
COPY --from=builder /bin/echo /bin/echo
COPY --from=builder /lib/ld-musl-*.so.1 /lib/
COPY --from=builder /tmp/entrypoint.sh /entrypoint.sh

# Copy config template (not final config) and credentials
COPY ./cwagent-config.json /opt/aws/amazon-cloudwatch-agent/bin/config.template.json
COPY ./credentials /root/.aws/credentials

ENV AWS_REGION=eu-central-1

# Override the base image ENTRYPOINT
ENTRYPOINT ["/entrypoint.sh"]

