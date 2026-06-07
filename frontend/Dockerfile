FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000
# Dev-Default (docker-compose). Für Produktion: `npm run build` + `npm start`
# (next.config.js: output "standalone") — auf Render via Node-Service (siehe render.yaml).
CMD ["npm", "run", "dev"]
