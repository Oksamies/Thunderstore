# Preliminary Investigation Report: Thunderstore Backend — Python 3.8/Django 3.1.7 → Python 3.14/Django 5.2

*Prepared 2026-07-24. Static analysis + web-verified. Where an adversarial verifier corrected a researcher, the verifier's finding is used and flagged.*

---

## 1. Verdict on the target

**The target is valid.** Django 5.2 supports Python 3.14 — but **not** in the 5.2.0 GA (April 2, 2025, which shipped 3.10–3.13). Python 3.14 support was added in the **5.2.8 patch** (Nov 5, 2025), verbatim: *"It also adds compatibility with Python 3.14."* A follow-up Py3.14 bug (NameError inspecting functions with deferred annotations, ticket #36903) was fixed in **5.2.12** (Mar 3, 2026). Verifier CONFIRMED all of this against primary sources.

- Django 5.2 release notes: *"supports Python 3.10, 3.11, 3.12, 3.13, and 3.14 (as of 5.2.8)"* — https://docs.djangoproject.com/en/5.2/releases/5.2/
- https://docs.djangoproject.com/en/6.0/releases/5.2.8/ · https://docs.djangoproject.com/en/6.0/releases/5.2.12/

**Concrete recommendation: pin Django to the latest 5.2.x (floor `>=5.2.12`), and land the port on Python 3.13 first, then flip the interpreter pin to 3.14 as an isolated follow-up.** Rationale: 3.13 is more battle-tested across the transitive C-extension stack, and Django 5.2 treats 3.13 and 3.14 identically as "supported," so nothing in the Django port depends on which one you run. This de-risks the single largest jump in the project by separating "does the code work on 5.2" from "do all native wheels exist for 3.14."

**LTS angle:** 5.2 **is** an LTS with security support into ~April 2028. Do **not** target Django 6.0 (released Dec 3, 2025) — it is a non-LTS 8-month release, drops Python 3.10/3.11, and buys **no** Py3.14 advantage over 5.2.8+. 5.2 also keeps the wider 3.10–3.14 range as fallback room. (Note: the PyPI Django page now shows 6.0.7 with classifiers 3.12–3.14 — that reflects 6.0.x, **not** 5.2; read the 5.2 range from the 5.2 release notes.)

**DRF floor:** DRF must move from the pinned **3.12.2** to **3.17.x** (latest 3.17.1). DRF 3.16 added Django 5.2 support; **Python 3.14 support landed in DRF 3.17.0**. See the drf-yasg caveat in §3.

---

## 2. Migration strategy — the key decision

The intermediate support windows force the ordering:

| Django | Python support window |
|---|---|
| 3.1 (current) | 3.6–3.9 (caps at 3.9) |
| 3.2 LTS | 3.6–3.10 |
| 4.2 LTS | 3.8–3.12 |
| 5.2 LTS | 3.10–3.14 |

There is **no single Python version that runs both the current Django (3.1, max 3.9) and the target (5.2, min 3.10).** That is the crux: you cannot bump Python and Django together in one atomic step.

**Recommendation: incremental LTS-to-LTS, with Python moving through the overlaps — not a big-bang.** A big-bang 3.1→5.2 jump means simultaneously absorbing distutils removal, the STORAGES refactor, CICharField removal, pydantic v2, and every dep major bump with no green test suite at any intermediate point. The incremental path keeps a runnable, test-passing state at each hop.

**Ordered sequence (each step ends green before the next):**

1. **Stay on Python 3.8/3.9, Django 3.1 → 3.2 LTS.** Small hop; clears `default_app_config` deprecation warnings surface here.
2. **Bump Python to 3.10 (or 3.11), still on the code you have, then Django 3.2 → 4.2 LTS.** 4.2 covers Python 3.8–3.12, so do the Python 3.10/3.11 bump *inside the 4.2 window*. **This is where distutils dies** — Python 3.12 removes it, so the StrictVersion/strtobool fixes (§4) can be done any time before you cross 3.12, but pin them here. Also here: STORAGES refactor is *available* (deprecated in 4.2) so you can migrate it now against a version that still accepts both forms.
3. **Bump Python to 3.13, then Django 4.2 → 5.2 LTS.** 5.2 requires Python ≥3.10; landing on 3.13 first is the safe floor. **This is where the hard removals bite:** CICharField (removed 5.1), the old `*_FILE_STORAGE`/`get_storage_class` (removed 5.1), `USE_L10N` (removed 5.0). pydantic v2, celery 5.6, gevent 26, pillow 12 all land in this step.
4. **Flip Python 3.13 → 3.14 as an isolated change.** Only native-wheel availability and pydantic-v2-on-3.14 matter here; the Django code is unchanged. Pin Django `>=5.2.12`.

**Why Python moves in step 2 and step 3, not step 1:** Django 3.1 caps at Python 3.9, so you're stuck below 3.10 until Django reaches 4.2. distutils forces you to be *off* the StrictVersion API before crossing Python 3.12, which naturally happens inside the 4.2 window. This ordering means each Python bump is validated against a Django version that officially supports it.

---

## 3. Dependency risk table (worst-first)

| Package | Current | Target | Status | Note |
|---|---|---|---|---|
| **pydantic** | ^1.9.0 | **v2 (>=2.x)** | 🔴 | **Verifier-CONFIRMED broken on 3.14.** v1 core silently breaks on Py3.14; the `pydantic.v1` shim does **not** rescue it. Real code migration across **12 modules** (`.json()`→`model_dump_json`, `.parse_obj()`→`model_validate`, `.parse_raw()`→`model_validate_json`, implicit-`Optional` fields become required). Also mis-declared under dev-deps but used at runtime. |
| **bleach** | 3.3.0 | **nh3 0.3.6** | 🔴 | Deprecated since 2023, sits on unmaintained html5lib. Migrate the **2 call sites** (`markdownify.py`, ts-scanners `package_source.py`). Behavior deltas: nh3 **strips** vs bleach **escapes** disallowed tags (snapshot-test), adds `rel="noopener"` by default, `protocols`→`url_schemes`, lists→sets, `attributes=["class"]` list-form → `{"span":{"class"}}`. |
| **pillow** | 8.3.2 | **^12.3** | 🟡 | No cp314 wheels below 11.3/12.0 — must jump 8→12. App's direct PIL use is trivial (stable APIs); real consumer is easy-thumbnails. |
| **gevent (+greenlet)** | 21.1.2 / 1.0.0 | **^26.7** | 🟡 | Old pair **will not build** on 3.14. gevent 26.7.0 ships cp314 wheels (pulls greenlet 3.2). Pin explicitly, don't rely on the ancient transitive resolve. |
| **celery** | 5.0.5 | **^5.6.3** | 🟡 | Py3.14 support first in 5.6.0. Large multi-minor jump; pulls kombu/billiard; config/behavior review needed. Move with django-celery-beat (→2.8.1) + results (→2.6.0). |
| **django-cachalot** | 2.3.3 | **>=2.9.0** | 🟡 | **Verifier: 2.9.0 is the floor** (2.8.0 lacks Py3.14). Config drop-in, but deep ORM/SQL-compiler hooks — smoke-test cache invalidation on 5.2. |
| **django-environ** | 0.4.5 | **0.14.0** | 🟡 | 8-yr jump. Inline-comment handling now **disabled by default** (`#` after a value is literal) — audit `.env`/`.env.template` for trailing comments and list parsing. |
| **sentry-sdk** | 1.31.0 | **2.66.1 [celery]** | 🟡 | 1.x→2.x rewrite: `init()` options changed, integrations auto-enabled. Read the 2.0 migration guide; touches the init site. |
| **arrow** | 0.17.0 | **^1.4** | 🟡 | 0.x→1.x major. `.timestamp` attribute→method silently breaks — grep every call site. |
| **easy-thumbnails** | 2.7.1 | **2.10.1** | 🟡 | 2.10.1 adds Django 5.2. **Re-diff the monkeypatch** (`monkeypatch_thumbnailer.py`, `thumbnail_exists`) against 2.10.1. Inherits the Pillow 12 requirement. |
| **django-redis** | 4.12.1 | **7.0.0** | 🟡 | Transitive redis-py 3.x→5.x major. Config drop-in; confirm multi-cache (default/legacy/profiles/downloads) connects. |
| **django-storages** | 1.12.3 | **1.14.6** | 🟡 | Rides the STORAGES refactor (§4). S3Boto3 backend unchanged; installs on 3.14 (no upper cap). |
| **whitenoise** | 5.2.0 | **6.12.0** | 🟡 | Clean package bump; carries the `STATICFILES_STORAGE`→`STORAGES["staticfiles"]` edit. |
| **social-auth-app-django** | ^5.0 | **6.0.1** | 🟡 | **Hard-requires Django>=5.2** — install *after* the Django bump. Pair with social-auth-core 5.0.2. Verify Overwolf custom backend + migrations. |
| **drf-yasg** | 1.20.0 | **1.21.15** | 🟡 | **Researcher said 🔴 "migrate to drf-spectacular"; verifier REFUTED it.** drf-yasg is maintained (1.21.15, Feb 2026), officially supports Django 5.2 + DRF 3.16 (tox-tested). **No spectacular migration needed for 5.2.** Only genuine risk: Py3.14 + DRF 3.17 are untested upstream (tox caps at Py3.13/DRF 3.16) — **validate `/api/docs/` in CI**. ~134 uses across 45 files make a spectacular switch expensive and avoidable now. |
| **djangorestframework** | 3.12.2 | **3.17.1** | 🟡 | Floor 3.16 for Django 5.2, 3.17 for Python 3.14. Repo doesn't touch removed CoreAPI. Coupled to the drf-yasg DRF-3.16 test ceiling above — verify the combination. |
| **confluent-kafka** | 2.11.1 | **2.15.0** | 🟡 | First cp314 wheels. API stable. Use standard GIL build (not free-threaded). |
| **lxml** | 4.9.1 | **^6.0.2** | 🟡 | First cp314 wheels at 6.0.1. Only `lxml.etree` used (2 sites) — near-zero code risk. |
| **uwsgi** | 2.0.30 | **2.0.31** | 🟡 | Source-build (no wheels); 2.0.30 already has the 3.14 port, 2.0.31 adds gcc-15 fixes. Docker image needs 3.14 dev headers. |
| **gunicorn** | 20.1.0 | **26.0.0** | 🟡 | Runs on 3.14 but **no official 3.14 testing** yet (discussion #3584). The gevent worker is the real gate. |
| **markdown-it-py** | 2.1.0 | **^4.2** | 🟡 | 2 majors; `gfm-like` preset survives. Snapshot-test render, especially with the bleach→nh3 change. |
| **ulid2** | 0.2.0 | **0.3.0** | 🟡 | Dormant but pure-Python; callable is baked into **migration files** — bump to 0.3.0 now, defer python-ulid migration. |
| **abyss** (git dep) | pinned rev | verify/vendor | 🟡 | Tracing profiler touching interpreter internals — **unverified on 3.14**. Non-critical middleware. Try pinned rev → re-pin HEAD → vendor/drop if broken. |
| **django-ipware** | 3.0.2 | 7.0.1 | 🟡 | Single call site, stable `(ip, routable)` signature. Stale (2024) but low risk. |
| django-celery-beat / -results | 2.2.0 / 2.0.1 | 2.8.1 / 2.6.0 | 🟡 | New migrations on their tables — run `migrate`. Lockstep with celery. |
| **psycopg2-binary** | 2.9.6 | **2.9.12** | 🟢 | cp314 wheels, zero code change. (psycopg3 optional follow-up.) |
| **django-cors-headers** | 3.7.0 | 4.9.0 | 🟢 | Repo already uses modern `CORS_ALLOWED_ORIGINS` — true drop-in. |
| pyjwt / pygments / boto3 | 2.0.1 / 2.16.1 / 1.17 | 2.13 / 2.20 / current 1.x | 🟢 | Effectively drop-in. (pyjwt's `cryptography` transitive dep also has cp314 wheels — confirm.) |

---

## 4. Code-change surface (R4 + R5)

### Blockers (build/import fails)

- **`distutils.version.StrictVersion`** — removed Python 3.12. **~14 occurrences** across 5 production modules (`package.py`, `cache.py`, `validators.py`, `package_reference.py`, `api/v1/serializers.py`), **3 data migrations** (0005, 0013, 0016 — imported eagerly by the migration loader), and 1 test. **The hardest correctness item.** Fix + **ordering-semantics caveat**: every string here is strictly `\d+\.\d+\.\d+` (enforced by `PACKAGE_VERSION_REGEX`), so StrictVersion's numeric ordering is reproduced **exactly** by `tuple(int(p) for p in s.split('.'))` (zero-dep, provably identical order — **preferred for sort keys**). `packaging.version.Version` also orders X.Y.Z identically but is only a *transitive* dep (must be made explicit) and is far more lenient — **do NOT drop it into `VersionNumberValidator` (validators.py:48)** without keeping an explicit `PACKAGE_VERSION_REGEX.fullmatch` gate, because that validator's entire purpose is StrictVersion's `ValueError` on bad input. `.version` (int-tuple, read at `package_reference.py:55`, `validators.py:49`) → `.release` on packaging, or join the int-tuple directly. Pin ordering with a unit test.
- **`distutils.util.strtobool`** — removed Python 3.12. `docker_entrypoint.py:5,66` (parses `RUN_MIGRATIONS`). Inline a 5-line helper; silent mis-parse of boot flags if left.
- **`CICharField`** — removed Django 5.1. `repository/models/namespace.py` — it's the `Namespace` **primary key**. Replace with `CharField` + a Postgres non-deterministic collation (`db_collation`) or a `Lower()` UniqueConstraint. New AlterField migration; heavier because it's a PK with FKs pointing at it. Historical migration 0028 keeps working (citext stub retained).
- **STORAGES refactor** — `get_storage_class()` + `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE`/six `*_FILE_STORAGE` strings removed Django 5.1. **~12 occurrences**: `core/settings.py` (L372, 659–664, 738–743, 788–798, 803–808), `core/storage.py`, and **4 model files** (`package_version.py`, `legacyprofile.py`, `blob.py`, `file.py`). **The largest single item.** Assemble one `STORAGES` dict (default/staticfiles/package/modpack/schema/blob/easy_thumbnails); in the 4 models use a **module-level callable** (`def get_package_storage(): return storages["package"]`, `FileField(storage=get_package_storage)`) so migrations serialize by reference and don't churn — this cleanly replaces the `get_storage_class_or_stub`/`StubStorage` makemigrations hack. One AlterField per field. easy-thumbnails: set `THUMBNAIL_DEFAULT_STORAGE_ALIAS`, move backend under STORAGES.

### Cleanup (non-fatal, delete dead config)

- **`USE_L10N = True`** — removed Django 5.0 (ignored). Delete `settings.py:384`.
- **`default_app_config`** — removed Django 4.1 (ignored). Delete from **13 app `__init__.py`** files; also drop it from `__all__` in `core/__init__.py`.

### Info

- **`DEFAULT_AUTO_FIELD` unset** — emits `models.W042` warnings. To silence *without schema change*, set `= "django.db.models.AutoField"` (do **not** use BigAutoField — that migrates every PK).
- **pytz in 7 migrations** — not a Python issue; keep pytz installed. Django 5.0 removed `USE_DEPRECATED_PYTZ` but these `CrontabSchedule.timezone=pytz.timezone("UTC")` values still work.

**Confirmed clean** (grep-verified absent): `url()`/`django.conf.urls`, `force_text`/`smart_text`, `ugettext`, `Signal(providing_args=)`, `NullBooleanField`, `request.is_ajax()`, `timezone.utc`, `index_together`, `python_2_unicode_compatible`, `six`, collections-ABC aliases, `inspect.getargspec`, `datetime.utcnow`, PEP-594 dead modules. `USE_TZ=True` and no `CSRF_TRUSTED_ORIGINS` — both default-flips are no-ops here.

---

## 5. Tooling / CI / Docker changes

- **Base image**: `python:3.8-slim-bullseye` → `python:3.14-slim-trixie` (Debian 13). Keep build-essential/git. Hard gate.
- **Poetry**: 1.4.2 (Docker) / 1.4.1 (CI) / 1.1.4 (devcontainer) → **2.4.x** (3.14 support only from Poetry 2.2). Drop the `virtualenv==20.7.2` pin.
- **pyproject**: `python = "^3.8"` → `"^3.14"` (unblocks the whole resolve). Modernize manifest: `[tool.poetry.dev-dependencies]` → `[tool.poetry.group.dev.dependencies]`, `poetry.masonry.api` → `poetry.core.masonry.api`, add `package-mode = false` (this is an app), move **pydantic into runtime deps**.
- **black**: 22.3.0 → **26.x** (confirmed: old black hits `asyncio.get_event_loop_policy()` removed on 3.14, psf/black#4718; pre-3.10 black won't install). `target-version=["py314"]`. Expect a large one-time reformat diff — land standalone. Matches memory note (host black crashes on Py3.14; run pre-commit in-container).
- **Ruff option**: recommend replacing flake8 3.8 + ~11 plugins with **Ruff** (native E/W/F, B, C4, A, COM, PIE, N, PT, YTT). flake8 hook is already commented out — net simplification and removes the biggest plugin-compat risk. Also subsumes isort.
- **mypy/stubs**: mypy `>=0.790` → **~1.18** (drf-stubs caps `<2.2`), django-stubs 1.7 → **6.0.7** (the 5.2.x stub line only supports Py≤3.13, so 6.0.x is required *despite* the app being on 5.2), drf-stubs 1.3 → **3.17.0**. CI mypy job masks failures with `|| :` but pins must still resolve.
- **pydantic**: v1.9 → **v2** (code migration, §3/§4).
- **pytest stack**: pytest 6.2 → **8.4.x**, pytest-django 4.1 → **4.12.0**, pytest-cov 2.8 → **6/7.x**, pytest-xdist 2.5 → **3.8.0**, pytest-split 0.8 → **0.11.0**, pytest-freezegun (abandoned) → **pytest-freezer** (drop-in `freezer` fixture, only 2 test files), factory-boy 3.2 → 3.3.x, Faker ^6 → 30.x+.
- **CI**: setup-python 3.8 → **3.14**; the pre-commit job runs on host Python so it must move. Node 14 → 20/22 LTS. Replace `::set-output` → `$GITHUB_OUTPUT`, codeql-action v1 → v3, bump checkout/setup-python/setup-node majors, install-poetry `version:` → 2.4.x.
- **Node builder stage** (tech debt, orthogonal): `node:12-alpine` + node-sass 4.12 still runs on its pinned image (output feeds only the **legacy** Django static assets; active FE is the separate Remix repo). Cannot be rebuilt on modern Node without node-sass→dart-sass. **Do not bundle into this upgrade** — flag separately. Same for devcontainer (`python:3.8-buster`) and the obsolete compose `version:` key.

---

## 6. Effort & risk estimate

| Workstream | Size | Est. (eng-days) |
|---|---|---|
| Django hop 3.1→3.2→4.2→5.2 (settings, checks, per-hop test cycles) | L | 6–10 |
| STORAGES refactor (settings + 4 models + migrations + easy-thumbnails) | L | 3–5 |
| distutils/StrictVersion + strtobool (prod + migrations + tests) | M | 2–3 |
| CICharField PK → collation | M | 2–3 |
| pydantic v1→v2 (12 modules) | L | 3–5 |
| bleach→nh3 (2 sites + snapshot regression) | S–M | 1–2 |
| Native-dep bumps (pillow/lxml/gevent/kafka/psycopg2/uwsgi) + wheel validation on 3.14 | M | 2–4 |
| celery/kombu/beat/results 5.0→5.6 + config review | M | 2–4 |
| Other dep bumps (sentry, redis, environ, arrow, social-auth, drf, drf-yasg) + behavior review | M | 3–5 |
| Tooling/CI/Docker/poetry/black/ruff/mypy/pytest | M | 3–5 |
| Full regression, CI stabilization, drf-yasg + Py3.14 smoke tests | L | 4–7 |
| **Overall** | | **~31–53 eng-days (~6–11 weeks, one engineer)** |

**Top 5 risks:**
1. **pydantic v2 migration** — runtime-critical paths (download view, Kafka), implicit-Optional fields silently become required; needs careful per-model review + tests.
2. **STORAGES refactor + storage migrations** — touches file-serving for packages/modpacks/blobs/schema; a wrong callable reference churns migrations or breaks prod S3.
3. **distutils/StrictVersion ordering semantics** — a naive `packaging.Version` swap into the validator weakens version validation; migrations import it eagerly (breaks test DB build) — must fix all 3.
4. **Py3.14 + DRF 3.17 + drf-yasg untested upstream** — the one combination no upstream tests; validate `/api/docs/` in CI, keep DRF-3.17-vs-drf-yasg-tested-3.16 in view.
5. **cachalot on Django 5.2** — deep ORM/SQL-compiler hooks; cache-invalidation correctness must be smoke-tested, not assumed.

---

## 7. Open decisions for the user

1. **Landing Python: 3.13 then 3.14, or straight to 3.14?** → **Recommend 3.13 first, 3.14 as an isolated follow-up.** Django treats them identically; this separates "code works on 5.2" from "all native wheels exist," de-risking the biggest jump. Pin Django `>=5.2.12`.
2. **Migration shape: incremental LTS-to-LTS or big-bang?** → **Recommend incremental (3.1→3.2→4.2→5.2)**, Python bumped inside the 4.2 window (past 3.12, killing distutils) then to 3.13 for 5.2. Keeps a green suite at every hop.
3. **drf-yasg: keep or migrate to drf-spectacular?** → **Keep drf-yasg, bump to 1.21.15** (verifier refuted the "must migrate" claim — it supports Django 5.2). Validate Py3.14 in CI. Treat drf-spectacular as a **separate, optional** OpenAPI-3 modernization (~134 uses = large refactor, avoidable now).
4. **psycopg2 or psycopg3?** → **Ship on psycopg2-binary 2.9.12** (drop-in, cp314 wheels). psycopg3 is a separate follow-up (autocommit/type-adaptation differences).
5. **uwsgi + gunicorn, or drop to one?** → **Decision point:** the repo ships both. gunicorn[gevent] 26 + gevent 26.7 gives a clean wheel-based path; uwsgi 2.0.31 needs a source build with 3.14 headers. **Recommend evaluating dropping uwsgi** to shed the source-build dependency — but only if nothing in deploy depends on it.
6. **flake8 stack or Ruff?** → **Recommend Ruff** (subsumes all ~11 plugins + isort, removes the largest 3.14 plugin-compat risk; flake8 hook is already disabled).
7. **pydantic v1→v2: now or shim?** → **Must be a real v2 migration** (verifier-confirmed: the `pydantic.v1` shim also breaks on 3.14). Not optional for this target.
8. **ulid2: bump or replace?** → **Bump to 0.3.0 now**, defer python-ulid (its callable is baked into migration files). 
9. **`DEFAULT_AUTO_FIELD`: set or leave?** → **Set to `AutoField`** to silence W042 without schema change. Do **not** use BigAutoField (migrates every PK).