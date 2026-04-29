#!/usr/bin/env bash
set -euo pipefail

export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"

stage_dir=".ci-android-src"
artifact_dir="bin"

rm -rf "$stage_dir" "$artifact_dir"
mkdir -p "$stage_dir" "$artifact_dir"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.buildozer/' \
  --exclude '.buildozer-venv/' \
  --exclude '.ci-buildozer-venv/' \
  --exclude '.ci-android-src/' \
  --exclude '.kivy_runtime/' \
  --exclude '.pytest_cache/' \
  --exclude '.qodo/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude 'node_modules/' \
  --exclude 'venv/' \
  --exclude 'Lib/' \
  --exclude 'DLLs/' \
  --exclude 'Doc/' \
  --exclude 'Scripts/' \
  --exclude 'Tools/' \
  --exclude 'include/' \
  --exclude 'libs/' \
  --exclude 'share/' \
  --exclude 'tcl/' \
  --exclude 'backend/' \
  --exclude 'frontend/' \
  --exclude 'kivy_frontend/' \
  --exclude 'admin-panel/' \
  --exclude 'Admin_Dashboard/' \
  --exclude 'BoG_Submission_Pack/' \
  --exclude 'Compliance_Policies/' \
  --exclude 'postgres_local/' \
  --exclude 'public/' \
  --exclude 'cyber_cash/' \
  --exclude 'bin/' \
  --exclude '.env' \
  --exclude '*.env' \
  --exclude '*.db' \
  --exclude '*.dll' \
  --exclude '*.exe' \
  --exclude '*.log' \
  --exclude '*.pdb' \
  --exclude '*.pyc' \
  --exclude 'session.json' \
  --exclude 'user_data.json' \
  ./ "$stage_dir/"

copy_paths=(
  app.py
  main.py
  app_config.json
  buildozer.spec
  requirements.txt
  api
  components
  core
  screens
  services
  storage.py
  theme.py
  utils
)

for path in "${copy_paths[@]}"; do
  if [ -e "$path" ]; then
    rsync -a "$path" "$stage_dir/"
  fi
done

if [ ! -f "$stage_dir/main.py" ]; then
  echo "Staged Android source is missing main.py" >&2
  find "$stage_dir" -maxdepth 2 -type f | sort >&2
  exit 1
fi

if [ ! -f "$stage_dir/app.py" ]; then
  echo "Staged Android source is missing app.py" >&2
  find "$stage_dir" -maxdepth 2 -type f | sort >&2
  exit 1
fi

echo "Staged Android entrypoint files:"
ls -l "$stage_dir/main.py" "$stage_dir/app.py"

python3 -m venv .ci-buildozer-venv
source .ci-buildozer-venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install "Cython<3" "buildozer==1.5.0"

pushd "$stage_dir" >/dev/null
buildozer android debug
popd >/dev/null

find "$stage_dir/bin" -maxdepth 1 \( -name '*.apk' -o -name '*.aab' \) -exec cp {} "$artifact_dir/" \;
