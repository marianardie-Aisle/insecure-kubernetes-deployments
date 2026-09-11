FROM node:16

# Create /app directory and set as working directory
RUN mkdir /app
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

# Create a dedicated writable directory for runtime data and make it owned by the unprivileged user
RUN mkdir -p /app/data && chown -R node:node /app/data

# Switch to the unprivileged 'node' user provided by the official Node image
USER node

EXPOSE 3000

# Run the database initialization script, then start the server as a non-root user
CMD ["/bin/bash", "-c", "node init_db.js && node server.js"]
