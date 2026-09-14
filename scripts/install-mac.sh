#!/bin/zsh
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="$HOME/.coffee-work"
mkdir -p "$HOME_DIR" "$HOME_DIR/bin"
chmod 700 "$HOME_DIR"
python3 -m venv "$HOME_DIR/venv"
"$HOME_DIR/venv/bin/pip" install -r "$PROJECT/requirements-mac.txt"
if [[ ! -e "$HOME_DIR/config.json" ]]; then cp "$PROJECT/config.example.json" "$HOME_DIR/config.json"; chmod 600 "$HOME_DIR/config.json"; fi
python3 - "$PROJECT" "$HOME_DIR" <<'PY'
import json,pathlib,sys,shlex
project, home = map(pathlib.Path, sys.argv[1:])
config_path = home/'config.json'
config = json.loads(config_path.read_text())
if not str(config.get('mac_project_dir') or '').strip():
    config['mac_project_dir'] = str(project)
config_path.write_text(json.dumps(config, indent=2) + '\n')
config_path.chmod(0o600)
wrapper = home/'bin/coffee-work'
wrapper.write_text('#!/bin/zsh\nexport PYTHONPATH=' + shlex.quote(str(project)) + '\nexec ' + shlex.quote(str(home/'venv/bin/python3')) + ' -m coffee_work.cli "$@"\n')
wrapper.chmod(0o700)
PY
printf 'Edit %s/config.json if needed. Calendar authentication comes from Plow Light/Latch; no Google OAuth file is needed for Calendar.\n' "$HOME_DIR"
printf 'Start the watcher from the agent checkout with: docker compose up --build -d\n'
printf 'Use %s/bin/coffee-work record start|stop for local meeting recording. Drive OAuth is requested only when publishing notes; then run %s/bin/coffee-work drive-auth if prompted.\n' "$HOME_DIR" "$HOME_DIR"
