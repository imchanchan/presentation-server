# presentation-server

## Docker usage

Build an image that contains everything needed for both the production server and the nodemon-based dev workflow.

```bash
docker build -t presentation-server .
```

Run the production server (`npm run server`) inside the container:

```bash
docker run --env-file .env -p 5000:5000 presentation-server
```

Run the nodemon watcher (`npm run dev`) inside the same image:

```bash
docker run --env-file .env -p 5000:5000 presentation-server dev
```

Pass any required environment variables (such as `MONGO_URI`) via `--env-file` or `-e` flags when running the container.
