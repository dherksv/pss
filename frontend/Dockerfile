FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies including optional ones (needed for rollup native binaries)
RUN npm ci && \
    npm cache clean --force

# Copy application files
COPY . .

EXPOSE 3000

# Use npm exec to run vite
CMD ["npm", "exec", "--", "vite", "--host", "0.0.0.0", "--port", "3000"]