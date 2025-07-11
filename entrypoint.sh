#!/bin/bash
set -e

# Use the HOST_USER_ID and HOST_GROUP_ID passed in, or default to 1000
HOST_USER_ID=${HOST_USER_ID:-1000}
HOST_GROUP_ID=${HOST_GROUP_ID:-1000}

# Modify the appuser's UID and GID to match the host user.
# This ensures that files created in mounted volumes have the correct ownership.
groupmod -g ${HOST_GROUP_ID} -o appuser
usermod -u ${HOST_USER_ID} -o appuser

# Now, drop root privileges and execute the command passed to this script (the Dockerfile CMD)
# as the correctly-mapped 'appuser'.
exec gosu appuser "$@"
