FROM node:18-alpine

WORKDIR /app

COPY frontend/package.json /app/package.json
COPY frontend/vite.config.js /app/vite.config.js
COPY frontend/index.html /app/index.html
COPY frontend/src /app/src

RUN npm install --silent

EXPOSE 5173

CMD ["sh","-lc","npm install && npm run dev -- --host 0.0.0.0"]
