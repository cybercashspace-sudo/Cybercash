#!/usr/bin/env bash
set -euo pipefail

export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"

stage_dir=".ci-android-src"
artifact_dir="bin"
app_src_dir="$stage_dir/android_app_src"

rm -rf "$stage_dir"
mkdir -p "$stage_dir" "$artifact_dir" "$app_src_dir"

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
    rsync -a "$path" "$app_src_dir/"
  fi
done

if [ ! -f "$app_src_dir/main.py" ]; then
  echo "Staged Android source is missing main.py" >&2
  find "$app_src_dir" -maxdepth 2 -type f | sort >&2
  exit 1
fi

if [ ! -f "$app_src_dir/app.py" ]; then
  echo "Staged Android source is missing app.py" >&2
  find "$app_src_dir" -maxdepth 2 -type f | sort >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path

spec_path = Path(".ci-android-src") / "buildozer.spec"
text = spec_path.read_text(encoding="utf-8")
updated = []
replaced = False
for line in text.splitlines():
    if line.startswith("source.dir ="):
        updated.append("source.dir = android_app_src")
        replaced = True
    else:
        updated.append(line)
if not replaced:
    raise SystemExit("buildozer.spec missing source.dir")
spec_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY

echo "Staged Android app source:"
find "$app_src_dir" -maxdepth 2 -type f | sort | head -n 60
echo "Staged Android entrypoint files:"
ls -l "$app_src_dir/main.py" "$app_src_dir/app.py"

python3 -m venv .ci-buildozer-venv
source .ci-buildozer-venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install "Cython<3" "buildozer==1.5.0"

git config --global http.version HTTP/1.1 || true
git config --global http.lowSpeedLimit 0 || true
git config --global http.lowSpeedTime 999999 || true
git config --global http.postBuffer 524288000 || true

pushd "$stage_dir" >/dev/null

p4a_parent_dir=".buildozer/android/platform"
p4a_dir="$p4a_parent_dir/python-for-android"
mkdir -p "$p4a_parent_dir"

if ! git -C "$p4a_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
   ! git -C "$p4a_dir" rev-parse --verify HEAD >/dev/null 2>&1; then
  rm -rf "$p4a_dir"
  echo "Pre-cloning python-for-android with retries..."
  for attempt in 1 2 3 4 5; do
    echo "python-for-android clone attempt $attempt/5"
    if git clone --depth 1 --single-branch --branch master https://github.com/kivy/python-for-android.git "$p4a_dir"; then
      break
    fi
    rm -rf "$p4a_dir"
    if [ "$attempt" -eq 5 ]; then
      echo "Failed to pre-clone python-for-android after multiple attempts." >&2
      exit 1
    fi
    sleep $((attempt * 10))
  done
fi

buildozer android debug
popd >/dev/null

shopt -s nullglob
artifacts=("$stage_dir"/bin/*.apk "$stage_dir"/bin/*.aab)

if [ "${#artifacts[@]}" -eq 0 ]; then
  echo "Build completed, but no APK or AAB was found in $stage_dir/bin" >&2
  exit 1
fi

cp -f "${artifacts[@]}" "$artifact_dir/"
echo "Android artifacts copied to $artifact_dir:"
for artifact in "${artifacts[@]}"; do
  echo " - $artifact_dir/$(basename "$artifact")"
done
