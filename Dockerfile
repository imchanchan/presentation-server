# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /usr/src/app

COPY package*.json ./
RUN npm ci

COPY . .

ENV PORT=5000
EXPOSE 5000

ENTRYPOINT ["npm", "run"]
CMD ["server"]
