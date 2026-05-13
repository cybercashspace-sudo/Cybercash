#!/usr/bin/env bash
set -euo pipefail

export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"

stage_dir="ci_android_src"
artifact_dir="bin"
app_src_dir="$stage_dir"

resolve_python_bin() {
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  return 1
}

copy_path() {
  local source_path="$1"
  local target_dir="$2"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "$source_path" "$target_dir/"
  else
    cp -a "$source_path" "$target_dir/"
  fi
}

sync_dir_contents() {
  local source_dir="$1"
  local target_dir="$2"
  shift 2
  local excludes=("$@")
  if command -v rsync >/dev/null 2>&1; then
    local rsync_args=(
      -a
      --delete
      --exclude '__pycache__/'
      --exclude '*.pyc'
    )
    for exclude_name in "${excludes[@]}"; do
      rsync_args+=(--exclude "${exclude_name}/")
    done
    rsync "${rsync_args[@]}" "$source_dir/" "$target_dir/"
  else
    local excluded=0
    find "$target_dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    while IFS= read -r -d '' entry; do
      local entry_name
      entry_name="$(basename "$entry")"
      if [ "$entry_name" = "__pycache__" ]; then
        continue
      fi
      if [[ "$entry_name" == *.pyc ]]; then
        continue
      fi
      excluded=0
      for exclude_name in "${excludes[@]}"; do
        if [ "$entry_name" = "$exclude_name" ]; then
          excluded=1
          break
        fi
      done
      if [ "$excluded" -eq 1 ]; then
        continue
      fi
      cp -a "$entry" "$target_dir/"
    done < <(find "$source_dir" -mindepth 1 -maxdepth 1 -print0)
  fi
}

if ! PYTHON_BIN="$(resolve_python_bin)"; then
  echo "No usable Python interpreter was found on PATH." >&2
  exit 1
fi

rm -rf "$stage_dir"
mkdir -p "$stage_dir" "$artifact_dir"

copy_path buildozer.spec "$stage_dir"

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
    copy_path "$path" "$app_src_dir"
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

STAGE_DIR="$stage_dir" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

stage_dir = Path(os.environ["STAGE_DIR"])
spec_path = stage_dir / "buildozer.spec"
text = spec_path.read_text(encoding="utf-8")
updated = []
replaced = False
for line in text.splitlines():
    if line.startswith("source.dir ="):
        updated.append("source.dir = .")
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

if [ "${CYBERCASH_ANDROID_STAGE_ONLY:-0}" = "1" ]; then
  echo "Stage-only mode complete; skipping Buildozer bootstrap and build."
  exit 0
fi

if [ -d /usr/lib/jvm/java-17-openjdk-amd64 ]; then
  export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
elif [ -d /usr/lib/jvm/temurin-17-jdk-amd64 ]; then
  export JAVA_HOME=/usr/lib/jvm/temurin-17-jdk-amd64
fi
if [ -z "${JAVA_HOME:-}" ]; then
  echo "JAVA_HOME is not set and no JDK 17 install was found." >&2
  exit 1
fi
export PATH="$JAVA_HOME/bin:$PATH"
java -version

"$PYTHON_BIN" -m venv .ci-buildozer-venv
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
private_app_dir=".buildozer/android/app"
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

seed_private_app_dir() {
  rm -rf "$private_app_dir"
  mkdir -p "$private_app_dir"
  sync_dir_contents "." "$private_app_dir" ".buildozer" "bin"
  if [ ! -f "$private_app_dir/main.py" ]; then
    echo "Private Android app dir is missing main.py after seeding." >&2
    find "$private_app_dir" -maxdepth 2 -type f | sort >&2
    exit 1
  fi
  echo "Seeded Android private app entrypoint:"
  ls -l "$private_app_dir/main.py" "$private_app_dir/app.py"
}

seed_private_app_dir

if ! buildozer android debug; then
  echo "Buildozer failed; private app dir contents:" >&2
  find "$private_app_dir" -maxdepth 2 -type f | sort | head -n 120 >&2 || true
  exit 1
fi
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
