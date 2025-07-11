# Stage 1: Build stage for installing dependencies
FROM python:3.12.3 AS build

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip setuptools \
    && pip install --require-hashes --no-cache-dir -r requirements.txt --verbose \
    && rm -rf /root/.cache/pip

COPY . /app


# Stage 2: Final slim image for production
FROM python:3.12.3-slim

# Install gosu, a lightweight tool for switching users, then clean up.
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed dependencies and application code
COPY --from=build /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

# Create a generic appuser with a standard home directory
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Combine the entrypoint script and the main command.
ENTRYPOINT ["entrypoint.sh", "python", "-u", "crews_control.py"]

# The default command is now empty, as the main command is in the ENTRYPOINT.
CMD []
