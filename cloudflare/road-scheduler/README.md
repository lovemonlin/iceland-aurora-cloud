# IRCA Road Scheduler

## Purpose

Triggers the existing `update-road-info.yml` publisher through its GitHub Actions dispatch endpoint.

## Architecture

Cloudflare Workers Cron Trigger → this Worker → GitHub Actions `workflow_dispatch` → existing IRCA publisher.

## Cron

`*/10 * * * *` (every ten minutes).

## Target

`lovemonlin/iceland-aurora-cloud`, workflow `update-road-info.yml`, ref `main`.

## Secret

The Worker reads `GITHUB_TOKEN` from its runtime environment. Do not place the token in source code,
`wrangler.toml`, or test fixtures.

## Local checks

After installing the development dependencies, run:

```sh
npm test
npm run typecheck
```

## Future production step

This directory contains source code only. Deployment is a separate production step.

When deployment is approved, the intended commands are:

```sh
npx wrangler secret put GITHUB_TOKEN
npx wrangler deploy
```
