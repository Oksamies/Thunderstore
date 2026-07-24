# Migration Plan — Thunderstore backend → Python 3.14 + Django 5.2

**Approach:** big-bang (no intermediate Django hops) · **Scope:** minimal-viable · **Branch:** `py314-django52`
**Companion:** [PY314_DJANGO52_INVESTIGATION.md](PY314_DJANGO52_INVESTIGATION.md) (full findings, sources, verifier notes)

Target pair: **Django `>=5.2.12,<5.3` (LTS)** + **Python 3.14**. Python 3.14 is supported by Django only from the 5.2.8 patch; 5.2.12 fixes a Py3.14 annotation bug — so 5.2.12 is the floor. DRF must be `>=3.17` for Py3.14.

> **De-risk lever (keep in pocket):** if the Poetry resolve / Docker build can't get cp314 wheels for every native dep, land on **Python 3.13** first (Django treats 3.13 and 3.14 identically), get green, then flip the interpreter pin to 3.14 as a one-line follow-up. Not the default path, but the escape hatch if wheels fight back.

## Scope boundary

**In scope** — everything required to build, boot, migrate, and test green on 5.2/3.14, including *version bumps* of existing tools (black, flake8, mypy, pytest) for 3.14 compatibility.

**Explicitly deferred to separate tasks** (do NOT bundle):
- drf-yasg → drf-spectacular (keep drf-yasg 1.21.15; it supports 5.2)
- psycopg2 → psycopg3 (keep psycopg2-binary)
- flake8 → Ruff (keep flake8, just bump it)
- `node:12-alpine` builder stage → dart-sass/modern node (feeds only legacy static assets; still builds on its pinned image)
- devcontainer Python bump · compose `version:` key removal
- `DEFAULT_AUTO_FIELD` → BigAutoField (would migrate every PK)

---

## Phase 0 — Baseline & harness

- [ ] Confirm work happens only in `C:\projects\riskidev\Thunderstore-py314-dj52` on branch `py314-django52`.
- [ ] Snapshot the current `django/poetry.lock` (we regenerate it in Phase 1) and record the current green test baseline for reference.
- [ ] Establish the iterate loop we'll use every phase: `docker build` → `manage.py check` → scoped `pytest`. (Per repo rules: run one pytest at a time, foreground, `--reuse-db`; pre-commit/black run **in-container**.)

**Exit:** clean branch, build harness confirmed.

---

## Phase 1 — Manifest & toolchain (make it RESOLVE)

Rewrite `django/pyproject.toml`:

- [ ] `python = "^3.8"` → `python = "^3.14"` (this alone unblocks resolving Django ^5.2 + modern tools).
- [ ] Bump every runtime pin to the targets in the [pin table](#target-pin-table) below. Add **`packaging`** as an explicit runtime dep (StrictVersion replacement). Replace **`bleach` → `nh3`**.
- [ ] **Move `pydantic` into runtime deps** (currently mis-filed under dev-deps) at `^2`.
- [ ] Modernize the manifest: `[tool.poetry.dev-dependencies]` → `[tool.poetry.group.dev.dependencies]`; build-backend `poetry.masonry.api` → `poetry.core.masonry.api`; add `package-mode = false` (this is an app, not a library).
- [ ] Dev tooling bumps (minimal-viable = bump, don't swap): black 26 (`target-version=["py314"]`), flake8 7.x + plugin bumps, mypy ~1.18 + django-stubs 6.0.7 + drf-stubs 3.17.0, pytest 8.4 stack, `pytest-freezegun` → `pytest-freezer`, factory-boy/Faker bumps, `jsonschema` un-cap (`<4.0.0` → current), django-debug-toolbar bump.
- [ ] Regenerate `poetry.lock` (in-container, Poetry 2.4).

**Exit:** `poetry lock` resolves and `poetry install` succeeds inside the new image.

---

## Phase 2 — Docker & CI (make it BUILD)

- [ ] `Dockerfile`: base `python:3.8-slim-bullseye` → `python:3.14-slim-trixie`, re-pin `@sha256`. Poetry `1.4.2` → `2.4.x`; drop the `virtualenv==20.7.2` pin. Keep `build-essential git` (needed for uwsgi/lxml/psycopg2 source paths). Leave the `node:12-alpine` builder stage untouched (deferred).
- [ ] `.pre-commit-config.yaml`: black 26, flake8 7.x + plugins, isort, prettier node hook bump.
- [ ] `.github/workflows/test.yml`: `setup-python` 3.8 → 3.14 (the pre-commit job runs on host Python — must move; pytest/mypy/migration jobs inherit the image). `install-poetry` → 2.4.x. Node 14 → 20. `::set-output` → `$GITHUB_OUTPUT`. Bump action majors (`checkout@v4`, `setup-python@v5`, `setup-node@v4`, `codeql-action@v3`).
- [ ] `docker/docker-compose.pytest.yml` + `.github/workflows/{release,deploy}.yml`: sanity-check for pinned Python/Poetry/Node.

**Exit:** `docker build` completes; container reaches the healthcheck.

---

## Phase 3 — Import/boot blockers (make `manage.py check` PASS)

These fail at import time — Django won't load until all are fixed.

### 3a. distutils removal (Python 3.12) — `blocker`
All version strings here are strictly `\d+\.\d+\.\d+` (enforced by `PACKAGE_VERSION_REGEX`, `repository/consts.py:6`), so **int-tuple ordering reproduces StrictVersion exactly** — preferred over `packaging.Version` for sort keys (zero-dep, provably identical order). Keep the regex gate in the validator so bad input still raises.
- [ ] `repository/package_reference.py:3,27,28,55,145` — drop `StrictVersion`; `.version` tuple attr → int-tuple.
- [ ] `repository/models/package.py:3,181` — sort key.
- [ ] `repository/models/cache.py:5,314` — sort key.
- [ ] `repository/api/v1/serializers.py:1,78` — sort key.
- [ ] `repository/validators.py:1,48` (`VersionNumberValidator`) — **keep `PACKAGE_VERSION_REGEX.fullmatch` gate**; the whole point is StrictVersion's `ValueError` on bad input.
- [ ] Data migrations `0005_migrate_update_dates.py`, `0013_package_cache_latest.py`, `0016_recache_versions.py` — imported eagerly on every `migrate`/test-DB build → same int-tuple fix.
- [ ] `docker_entrypoint.py:5,66` — `distutils.util.strtobool` removed; inline a 5-line helper (parses `RUN_MIGRATIONS`; silent mis-parse of boot flags if wrong).
- [ ] `repository/tests/test_package_reference.py:1,199` — rewrite off StrictVersion.
- [ ] **Add a unit test pinning version ordering** (guards the semantics swap).

### 3b. CICharField PK (Django 5.1) — `blocker`
- [ ] `repository/models/namespace.py:1,14` — `Namespace.name` is the **primary key** via `CICharField`. Replace with `CharField(max_length=64)` + a Postgres **non-deterministic collation** (`db_collation`) — or drop DB-level CI and rely on the existing `name__iexact` lookups. New `AlterField` migration; heavier because FKs point at this PK. Historical migration `0028_namespace.py` keeps working (citext stub retained).

### 3c. STORAGES refactor (Django 5.1) — `blocker`, largest single item
`get_storage_class()` + `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE`/six `*_FILE_STORAGE` strings are gone.
- [ ] `core/settings.py` (L372, 659–664, 738–743, 788–798, 803–808) — assemble one `STORAGES` dict: `default`, `staticfiles` (whitenoise), `package`, `modpack`, `schema`, `blob`, easy-thumbnails. Preserve the FileSystem / S3Boto3 / MirroredS3 env-driven selection.
- [ ] `core/storage.py:13` — replace `get_storage_class_or_stub` / `StubStorage` makemigrations hack.
- [ ] Model `FileField`s use **module-level storage callables** (`def get_package_storage(): return storages["package"]`) so migrations serialize by reference and don't churn:
  - `repository/models/package_version.py:149` (`PACKAGE_FILE_STORAGE`)
  - `modpacks/models/legacyprofile.py:106` (`MODPACK_FILE_STORAGE`)
  - `storage/models/blob.py:26` (`BLOB_FILE_STORAGE`)
  - `schema_server/models/file.py:21` (`SCHEMA_FILE_STORAGE`)
- [ ] easy-thumbnails: set `THUMBNAIL_DEFAULT_STORAGE_ALIAS`, move its backend under `STORAGES`.
- [ ] `core/tests/test_storage.py:21` — update for the new API.
- [ ] Verify the resulting `AlterField` migrations are **reference-only** (no data migration).

### 3d. Settings cleanups
- [ ] Delete `USE_L10N = True` (`settings.py:384`, removed Django 5.0).
- [ ] Delete `default_app_config` from 13 app `__init__.py` files; also drop it from `__all__` in `core/__init__.py:5` (each app has exactly one AppConfig → auto-discovered).
- [ ] Set `DEFAULT_AUTO_FIELD = "django.db.models.AutoField"` to silence `models.W042` **without** a schema change (do NOT use BigAutoField).

**Exit:** `manage.py check` clean; `makemigrations --check` clean.

---

## Phase 4 — Dependency behavior changes (make it RUN correctly)

Major-version behavior deltas — verify, don't assume.

- [ ] **pydantic v1 → v2** (runtime-critical). 12 modules import pydantic; migrate `.parse_obj()` → `model_validate`, `.parse_raw()` → `model_validate_json`, `.dict()` → `model_dump`, `.json()` → `model_dump_json`, `@validator` → `@field_validator`, `class Config` → `model_config`, and **implicit-`Optional` fields become required** (add `= None`). Prioritize hot paths: `repository/views/package/download.py:26`, `ts_analytics/kafka.py`, `social/providers.py` (7 `parse_obj` sites), `social/api/experimental/views/overwolf.py`, `webhooks/tasks/audit.py:13` (`parse_raw`), `schema_import/sync.py:136`. Full list: modpacks/experimental legacyprofile, repository/tasks/downloads, schema_import/schema, social current_user/overwolf/providers, ts_analytics kafka/signals, webhooks audit/discord.
- [ ] **bleach → nh3** — 2 sites: `markdown/templatetags/markdownify.py` and `python-packages/ts-scanners/.../package_source.py`. Map `tags`/`attributes`(lists → sets, `{"span":{"class"}}`)/`protocols` → `url_schemes`; nh3 **strips** vs bleach **escapes**, adds `rel="noopener"`. **Snapshot-test** the rendered output.
- [ ] **easy-thumbnails 2.10.1** — re-diff `monkeypatch/monkeypatch_thumbnailer.py` (`Thumbnailer.thumbnail_exists`) against upstream 2.10.1; the patched method must still match the new source shape.
- [ ] **sentry-sdk 2.x** — `init()` options changed, integrations auto-enabled. Update the init site per the 2.0 migration guide.
- [ ] **django-environ 0.14** — inline `#` comments after a value are now literal by default. Audit `.env` / `.env.template` for trailing comments and list parsing.
- [ ] **arrow 1.x** — `.timestamp` attribute → method. Grep every call site (silent breakage).
- [ ] **django-redis 7 (redis-py 5)** — confirm the multi-cache config (default/legacy/profiles/downloads) connects.
- [ ] **celery 5.6 + beat 2.8.1 + results 2.6.0** — config/behavior review; run `migrate` (new migrations on their tables).
- [ ] **social-auth-app-django 6.0.1 + core 5.0.2** — install *after* the Django bump (hard-requires Django ≥5.2). Verify the Overwolf custom backend + its migrations.
- [ ] **markdown-it-py 4.x** — `gfm-like` preset survives; snapshot-test render (esp. with the nh3 change).
- [ ] **django-cachalot 2.9.0** — deep ORM hooks; smoke-test cache invalidation on 5.2.
- [ ] **abyss** (git dep, tracing profiler touching interpreter internals) — verify on 3.14; if broken, re-pin HEAD → else vendor/drop (non-critical middleware).

**Exit:** app boots, admin loads, key endpoints respond, `migrate` runs clean.

---

## Phase 5 — Test suite green

- [ ] Fix pytest collection: `test_package_reference.py` (StrictVersion), pydantic test behavior, `pytest-freezegun` → `pytest-freezer` `freezer` fixture rename (2 test files).
- [ ] Run full `pytest` (Docker, 6 split groups), fix failures iteratively (one suite at a time, foreground, `--reuse-db`).
- [ ] `mypy` with django-stubs 6 / drf-stubs 3.17 — CI masks with `|| :`, but pins must resolve; fix egregious new errors.
- [ ] **drf-yasg smoke test** — hit `/api/docs/` (Swagger) + schema JSON. This is the one combo untested upstream (Py3.14 + DRF 3.17 + drf-yasg 1.21.15); validate it explicitly.

**Exit:** pytest green across all groups; `makemigrations --check` clean; API docs render.

---

## Phase 6 — Verification & handoff

- [ ] Full acceptance: build → boot → migrate → pytest → makemigrations --check → mypy resolves → `/api/docs/` renders → admin + key endpoints manual smoke.
- [ ] Deliver uncommitted diffs on `py314-django52` for review (no commit trailer, per repo convention).
- [ ] List Developer-Action items (env var changes from `django-environ`/sentry, migration runs).

---

## Risk register

1. **pydantic v2** — implicit-Optional fields silently become required on hot paths (downloads, Kafka, social). Per-model review + tests.
2. **STORAGES + storage migrations** — wrong callable reference churns migrations or breaks prod S3 file-serving.
3. **StrictVersion ordering** — a naive `packaging.Version` swap into the validator weakens validation; migrations import it eagerly (breaks test-DB build). Fix all sites + pin with a test.
4. **Py3.14 + DRF 3.17 + drf-yasg** — no upstream test coverage; validate docs in CI.
5. **cachalot on 5.2** — cache-invalidation correctness must be smoke-tested, not assumed.
6. **Native wheels on cp314** — pillow/lxml/gevent/kafka/uwsgi; the 3.13-fallback lever covers this.

---

## Target pin table

| Package | Current | Target | Note |
|---|---|---|---|
| Django | 3.1.7 | `>=5.2.12,<5.3` | LTS; 5.2.12 floor for Py3.14 |
| djangorestframework | 3.12.2 | `^3.17.1` | 3.17 required for Py3.14 |
| drf-yasg | 1.20.0 | `1.21.15` | **kept** (supports 5.2); spectacular deferred |
| pydantic | ^1.9 (dev) | `^2` (runtime) | real v2 migration; move to runtime deps |
| bleach | 3.3.0 | **`nh3 ^0.3.6`** | replace (bleach archived) |
| packaging | — (transitive) | explicit | StrictVersion replacement helper |
| pillow | 8.3.2 | `^12.3` | first cp314 wheels |
| lxml | 4.9.1 | `^6.0.2` | first cp314 wheels |
| gevent | 21.1.2 | `^26.7` | pulls greenlet 3.2; won't build old on 3.14 |
| gunicorn | 20.1.0 | `26.0.0` [gevent] | |
| uwsgi | 2.0.30 | `2.0.31` | source build; needs 3.14 dev headers |
| celery | 5.0.5 | `^5.6.3` | Py3.14 from 5.6.0 |
| django-celery-beat / -results | 2.2.0 / 2.0.1 | `2.8.1` / `2.6.0` | lockstep with celery |
| confluent-kafka | 2.11.1 | `2.15.0` | first cp314 wheels |
| psycopg2-binary | 2.9.6 | `2.9.12` | **kept**; cp314 wheels |
| easy-thumbnails | 2.7.1 | `2.10.1` | re-diff monkeypatch |
| django-storages | 1.12.3 | `1.14.6` [boto3] | rides STORAGES refactor |
| whitenoise | 5.2.0 | `6.12.0` | |
| django-redis | 4.12.1 | `7.0.0` | redis-py 5.x |
| django-environ | 0.4.5 | `0.14.0` | inline-comment behavior change |
| sentry-sdk | 1.31.0 | `2.66.1` [celery] | init() API rewrite |
| arrow | 0.17.0 | `^1.4` | `.timestamp` attr→method |
| social-auth-app-django / -core | ^5.0 / 4.1 | `6.0.1` / `5.0.2` | install after Django bump |
| django-cors-headers | 3.7.0 | `4.9.0` | drop-in |
| django-cachalot | 2.3.3 | `>=2.9.0` | smoke-test invalidation |
| django-ipware | 3.0.2 | `7.0.1` | single call site |
| markdown-it-py | 2.1.0 | `^4.2` [linkify] | |
| pyjwt | 2.0.1 | `~2.13` [crypto] | |
| pygments | 2.16.1 | `~2.20` | |
| ulid2 | 0.2.0 | `0.3.0` | callable baked in migrations |
| abyss (git) | pinned rev | verify/re-pin/vendor | unverified on 3.14 |
| **Dev** | | | |
| black | 22.3.0 | `26.x` (`py314`) | old crashes on 3.14 asyncio |
| flake8 (+plugins) | 3.8 | `7.x` | **kept** (Ruff deferred) |
| mypy / django-stubs / drf-stubs | 0.79 / 1.7 / 1.3 | `~1.18` / `6.0.7` / `3.17.0` | |
| pytest (+django/cov/xdist/split) | 6.2 / 4.1 / 2.8 / 2.5 / 0.8 | `8.4` / `4.12` / `~7` / `3.8` / `0.11` | |
| pytest-freezegun | 0.4.2 | **`pytest-freezer`** | abandoned → replace |
| factory-boy / Faker | 3.2 / ^6 | `3.3.x` / `30+` | |
| Poetry (Docker/CI) | 1.4 | `2.4.x` | 3.14 support from 2.2 |
