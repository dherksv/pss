FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

# Ensure vite binary is executable
RUN chmod +x node_modules/.bin/vite

COPY . .

EXPOSE 3000

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "3000"]