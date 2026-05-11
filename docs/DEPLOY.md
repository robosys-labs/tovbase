# Deploying tovbase to production

Production runs at https://tovbase.com — backed by a self-hosted GHA runner on the production server. **No manual SSH-from-laptop deploy needed any more.** This doc explains how the pipeline works and how to operate it.

## Quickstart

| Need | Command |
|------|---------|
| Deploy main now | `gh workflow run "Deploy to production"` |
| Deploy main + rebuild web container | `gh workflow run "Deploy to production" -f skip_web=false` |
| Watch the in-flight deploy | `gh run watch` |
| Check production health | `curl -s https://tovbase.com/v1/health` |
| List recent deploys | `gh run list --workflow=deploy.yml` |
| Tail backend logs | `ssh -i ~/Pictures/Wedding/venserve.pem -p 1145 venservant@158.220.87.109 "docker logs -n 200 -f tovbase-backend-1"` |

## How auto-deploy works

```
                                ┌──────────────────────────────────┐
                                │ Self-hosted GHA runner           │
                                │ ~/actions-runner-tovbase/        │
                                │ label: self-hosted,linux,x64,    │
                                │        tovbase                   │
                                │ libicu shim: ~/icu-libs/usr/lib64│
                                │ keep-alive: cron @reboot + */5   │
                                └────────────┬─────────────────────┘
                                             │
            push to main                     ▼
            (paths: app/, scripts/,     ┌─────────┐         docker compose
             pyproject.toml,            │ GHA job │ ─────►  on host (via   ─►  rebuilt containers
             seeds/, corpus/) ────────► │  runs   │         mounted socket)
                                        └─────────┘
            workflow_dispatch                ▲
                                             │
                                          rsync code
                                          into REMOTE_DIR
```

The runner lives on the server itself (label `tovbase`). When you push to `main` touching the watched paths, GitHub picks the runner, the runner rsyncs the checked-out code into `/home/venservant/tovbase/`, then runs `docker compose -f docker-compose.prod.yml build backend celery-worker celery-beat` directly. No SSH involved — the runner already IS the server.

## What the workflow does

[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Eight steps:

1. **Check out** — `actions/checkout@v4` pulls main into the runner's `_work` dir.
2. **rsync into REMOTE_DIR** — mirror of `scripts/deploy.py` DEPLOY_EXCLUDES. Production-owned files (Dockerfile, docker-compose.prod.yml, nginx.conf, migrations/) stay on the server.
3. **Build images** — `docker compose ... build --pull backend celery-worker celery-beat`. Web container is skipped by default (production-divergent tree).
4. **Bring up data deps** — postgres + redis + qdrant, sleep 8s for healthcheck.
5. **Run schema migration** — `scripts/migrate_v12.py` if present (idempotent ALTER TABLE).
6. **Start app** — `docker compose up -d backend celery-worker celery-beat`.
7. **Health check** — curl `127.0.0.1:9010/v1/health` with 5 retries. Tail backend logs on failure.
8. **Optional web rebuild** — only when `workflow_dispatch` with `skip_web=false`.

## What triggers an auto-deploy

Watched paths in [.github/workflows/deploy.yml](../.github/workflows/deploy.yml):
- `app/**`
- `scripts/**`
- `pyproject.toml`
- `seeds/**`
- `corpus/**`
- `.github/workflows/deploy.yml`

Anything else — `web/**`, `docs/**`, `tests/**`, README, etc. — pushes without triggering deploy.

## Pre-merge test gate

[`.github/workflows/test.yml`](../.github/workflows/test.yml) runs on **every PR and every push to main**. Hosted ubuntu-latest, ~60s. Three checks:

1. Python import smoke (`from app.api.routes import router`)
2. Ruff lint on `app/`, `scripts/` (non-blocking, visibility-only)
3. Pytest on the offline test subset (`test_scoring.py`, `test_similarity.py`, `test_vector.py`)

PRs are blockable on the import smoke — if `from app.api.routes import router` fails, the merge should be held.

## Repo secrets

Set via `gh secret set`. The self-hosted runner doesn't need any — it already runs on the server. The secrets remain as a fallback should we ever want to deploy from a hosted runner.

| Secret | Purpose |
|--------|---------|
| `SSH_PRIVATE_KEY` | Server SSH key (unused by self-hosted runner; held for future fallback) |
| `SSH_HOST` | `158.220.87.109` |
| `SSH_PORT` | `1145` |
| `SSH_USER` | `venservant` |
| `REMOTE_DIR` | `/home/venservant/tovbase` |

## Runner operations

```bash
# SSH into the server (only operator action that requires it)
ssh -i ~/Pictures/Wedding/venserve.pem -p 1145 venservant@158.220.87.109

# Runner status — is it listening?
cd ~/actions-runner-tovbase
pgrep -af Runner.Listener
tail -f runner.log

# Manually restart the runner
./watchdog.sh   # idempotent; only starts if not already running

# Check the keep-alive cron
crontab -l | grep watchdog

# Pull a fresh registration token (when re-registering or rotating)
# Requires `gh` on a machine with workflow scope:
gh api -X POST repos/robosys-labs/tovbase/actions/runners/registration-token --jq .token
```

The runner is wired to:
- `@reboot ~/actions-runner-tovbase/watchdog.sh`
- `*/5 * * * * ~/actions-runner-tovbase/watchdog.sh`

So a server reboot or a crashed runner self-recovers within 5 minutes.

## Production-owned files (DO NOT overwrite from local)

The CI workflow's `rsync --exclude` list mirrors `scripts/deploy.py` DEPLOY_EXCLUDES. These files live on the server and the CI never touches them:

- `docker-compose.prod.yml` — production compose with celery-worker + celery-beat + web + env wiring
- `docker-compose.yml` — dev compose (kept around)
- `nginx.conf` — server-side nginx config
- `Dockerfile`, `Dockerfile.worker`, `web/Dockerfile`
- `migrations/` — alembic state (currently empty but reserved)
- `.env` — server secrets
- `data/` — runtime state
- `app.backup.*`, `app_patch_staging`, `_patch` — operational rollback bundles

If you need to change any of these, SSH in and edit them directly, then commit a note to `docs/DEPLOY.md` about the change.

## Rolling back

The deploy doesn't snapshot the previous container. To roll back:

1. `git revert <bad-commit>` on main → push → CI rebuilds the previous version.
2. Or SSH into the server and `docker compose ... up -d backend` against a previously tagged image (if you tagged before deploying).

For irreversible changes (schema migrations), rollback requires the inverse migration script. Phase B1 schema migrations are additive-only (`ALTER TABLE ADD COLUMN`), safe to leave in place.

## Web container

Production's `web/` source tree carries features (claim-email flow) that aren't in main. The default deploy path SKIPs web rebuild. To rebuild it explicitly:

```bash
gh workflow run "Deploy to production" -f skip_web=false
```

But expect the build to fail if main's `web/` doesn't have the production-side files. Fix path: bring the production web/ tree fully into main first, then enable web rebuilds by default.

## Extension distribution

Backend serves the bundled Chrome extension zip directly so the install link works regardless of web container state:

- https://tovbase.com/v1/download/extension/tovbase-extension-latest.zip
- https://tovbase.com/v1/download/extension/tovbase-extension-v0.4.0.zip

Files ship inside the backend image at `app/static/`. When you publish a new extension version, drop the new zip into `app/static/`, bump the version in `extension/manifest.json`, force-add it to git (`.gitignore` matches `*.zip`), and the next push to main auto-deploys.

## Troubleshooting

| Symptom | First check |
|---------|-------------|
| `gh run watch` shows "Connection timed out" | The runner is offline. SSH to server, `pgrep -af Runner.Listener`, run `~/actions-runner-tovbase/watchdog.sh` if missing. |
| `gh run view ... --log-failed` shows "host *** port ***: Connection timed out" | Workflow accidentally ran on `runs-on: ubuntu-latest`. Check the workflow file specifies `[self-hosted, tovbase]`. |
| Health check fails after deploy | `ssh ... "docker logs -n 200 tovbase-backend-1"`. Common cause: new column reference + missing migration. Re-run with `scripts/migrate_v12.py` in the codebase. |
| New endpoint returns 404 after deploy | Verify backend uptime — `docker ps --filter name=tovbase`. If backend uptime is days, the deploy didn't restart it (path filter didn't match). Push something under `app/` or run `gh workflow run` manually. |
| Extension download returns 404 | Verify the zip is in `app/static/` in main (check with `git ls-files app/static/`) and was committed (zip files are normally gitignored — they need `git add -f`). |
