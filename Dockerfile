# Stage 1: Build and compile everything in a full Python image
FROM python:3.12 as build

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file, to cache the installed packages layer
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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

# Copy user settings to maintain the same user in the new stage
COPY --from=build /etc/passwd /etc/passwd

# Ensure the appuser owns the necessary directories
RUN mkdir -p /home/appuser && \
    chown -R appuser:appuser /home/appuser && \
    chown -R appuser:appuser /app

# Set the working directory and user
WORKDIR /app
USER appuser
