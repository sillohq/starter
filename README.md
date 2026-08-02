# Starter

A [Sillo](https://github.com/sillohq/core) application.

## Requirements

- Python >=3.11

## Getting started

```bash
cp .env.example .env
uv sync
sillo-start migrate run
sillo-start admin create-user
sillo-start dev
```

`sillo-start dev` starts every service this project needs.

| Service | URL |
| ------- | --- |
| Application | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Admin | http://localhost:8000/admin |

## Layout

```text
starter/
├── app/
│   ├── bootstrap.py      # assembles the application
│   ├── config.py         # typed settings loaded from .env
│   └── main.py           # ASGI entrypoint
├── database/
│   ├── models/           # Record models
│   └── migrations/       # generated migrations
├── routes/               # routers mounted onto the app
├── storage/              # logs, cache, uploads
├── tests/
├── pyproject.toml
└── sillo.toml            # project manifest — read by sillo-start
```

## Common commands

```bash
sillo-start dev                       # run everything
sillo-start dev --only backend        # run one service
sillo-start migrate make -m "add posts"
sillo-start migrate run
sillo-start generate model Post
sillo-start doctor                    # diagnose the project
sillo-start inspect                   # show configuration
pytest                                # run the test suite
```
