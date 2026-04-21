#!/usr/bin/env bash
# Bootstrap local dev: venv, pip install, optional docker db, migrate.
set -euo pipefail
PKG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Directory on PYTHONPATH (contains child folder `problem_discovery`)
SRC_DIR="$(cd "$PKG_ROOT/.." && pwd)"
VENV="$PKG_ROOT/.venv"
PY="$VENV/bin/python"

# Repo root: first ancestor of PKG_ROOT that contains docker-compose.yml (optional)
REPO_ROOT="$PKG_ROOT"
SEARCH="$PKG_ROOT"
while [[ "$SEARCH" != "/" ]]; do
  if [[ -f "$SEARCH/docker-compose.yml" ]]; then
    REPO_ROOT="$SEARCH"
    break
  fi
  SEARCH="$(dirname "$SEARCH")"
done

echo "REPO_ROOT=$REPO_ROOT"
echo "PKG_ROOT=$PKG_ROOT"
echo "SRC_DIR=$SRC_DIR (PYTHONPATH)"

if [[ ! -f "$REPO_ROOT/.env" ]] && [[ ! -f "$PKG_ROOT/.env" ]]; then
  if [[ -f "$PKG_ROOT/.env.example" ]]; then
    cp "$PKG_ROOT/.env.example" "$PKG_ROOT/.env"
    echo "Created $PKG_ROOT/.env from .env.example"
  elif [[ -f "$REPO_ROOT/.env.example" ]]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "Created $REPO_ROOT/.env from .env.example"
  else
    echo "Create $PKG_ROOT/.env with DATABASE_URL=..."
  fi
fi

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -U pip
pip install -r "$PKG_ROOT/requirements.txt"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1 && [[ -f "$REPO_ROOT/docker-compose.yml" ]]; then
    TMP_COMPOSE="$(mktemp -d)/docker-compose.yml"
    cp "$REPO_ROOT/docker-compose.yml" "$TMP_COMPOSE"
    docker compose -f "$TMP_COMPOSE" up -d || echo "Docker Postgres not started (install/start Docker or set DATABASE_URL to an existing server)."
    echo "Waiting for Postgres..."
    sleep 3
  fi
fi

cd "$PKG_ROOT"
set +e
"$PY" run_signal.py migrate
MIGRATE_RC=$?
set -e
if [[ $MIGRATE_RC -ne 0 ]]; then
  echo "migrate exited $MIGRATE_RC — ensure Postgres is up and .env has DATABASE_URL, then:"
  echo "  cd \"$PKG_ROOT\" && \"$PY\" run_signal.py migrate"
fi

echo "Done. Streamlit: cd \"$PKG_ROOT\" && source .venv/bin/activate && streamlit run streamlit_app.py"
echo "Or: make -C \"$PKG_ROOT\" streamlit"
echo "CLI: cd \"$PKG_ROOT\" && \"$PY\" run_signal.py collect-hn"
