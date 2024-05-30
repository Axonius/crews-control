# Stage 1: Build and compile everything in a full Python image
FROM python:3.12 as build

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file, to cache the installed packages layer
COPY requirements.txt /app/

# Install system dependencies for building packages (if any needed)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies with retries
RUN pip install --upgrade pip setuptools \
    && pip install --require-hashes --no-cache-dir -r requirements.txt --verbose
# Suggested retry mechanism for pip install (commented out)
# RUN pip install --upgrade pip setuptools && \
#     pip install --require-hashes --no-cache-dir -r requirements.txt || \
#     pip install --require-hashes --no-cache-dir -r requirements.txt


# Invalidate cache from here onwards when needed
ARG CACHEBUSTER=1

# Create a non-root user 'appuser' and switch to it
RUN groupadd appuser && \
    useradd -m -g appuser appuser

USER appuser

# Copy the current directory contents into the container at /app
COPY . /app

# Stage 2: Create a slim image for running the application
FROM python:3.12-slim

# Copy user and group data
COPY --from=build /etc/passwd /etc/passwd
COPY --from=build /etc/group /etc/group

# Copy installed Python packages from build stage
COPY --from=build /usr/local/lib/python3.12 /usr/local/lib/python3.12

# Ensure scripts in /usr/local/bin are available
COPY --from=build /usr/local/bin /usr/local/bin

# Copy application code and other necessary files from build stage
COPY --from=build /app /app

# Ensure the appuser owns the necessary directories
RUN mkdir -p /home/appuser && \
    chown -R appuser:appuser /home/appuser && \
    chown -R appuser:appuser /app

# Set the working directory and user
WORKDIR /app
USER appuser

ENTRYPOINT [ "python", "crews_control.py" ]
CMD []