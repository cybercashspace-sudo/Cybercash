#!/usr/bin/env bash
set -euo pipefail

if [ -z "${JAVA_HOME:-}" ]; then
  if [ -d /usr/lib/jvm/java-17-openjdk-amd64 ]; then
    export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
  elif [ -d /usr/lib/jvm/temurin-17-jdk-amd64 ]; then
    export JAVA_HOME=/usr/lib/jvm/temurin-17-jdk-amd64
  fi
  if [ -z "${JAVA_HOME:-}" ]; then
    echo "JAVA_HOME is not set and no JDK 17 install was found." >&2
    exit 1
  fi
fi
export PATH="$JAVA_HOME/bin:$PATH"
java -version
export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"

stage_dir="ci_android_src"
artifact_dir="bin"
app_src_dir="$stage_dir"

rm -rf "$stage_dir"
mkdir -p "$stage_dir" "$artifact_dir"

copy_paths=(
  buildozer.spec
  app.py
  kivy_app.py
  main.py
  app_config.json
  api
  assets
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
    rsync -a \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude 'test_*.py' \
      --exclude '*_test.py' \
      "$path" "$app_src_dir/"
  fi
done

# Trim backend-only helpers from the Android staging tree.
rm -f \
  "$app_src_dir/screens/virtual_card.py" \
  "$app_src_dir/screens/statement_service.py" \
  "$app_src_dir/utils/security.py"

if [ ! -f "$app_src_dir/main.py" ]; then
  if [ -f "$app_src_dir/kivy_app.py" ]; then
    echo "Auto-generating main.py shim for kivy_app.py..."
    cat <<EOF > "$app_src_dir/main.py"
from kivy_app import CyberCashApp
if __name__ == "__main__":
    CyberCashApp().run()
EOF
  else
    echo "Staged Android source is missing main.py and no kivy_app.py found to shim." >&2
    exit 1
  fi
fi

if [ ! -f "$app_src_dir/kivy_app.py" ]; then
  echo "Staged Android source is missing kivy_app.py" >&2
  find "$app_src_dir" -maxdepth 2 -type f | sort >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path

spec_path = Path("ci_android_src") / "buildozer.spec"
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
ls -l "$app_src_dir/main.py" "$app_src_dir/app.py" "$app_src_dir/kivy_app.py"

python3 -m venv .ci-buildozer-venv
source .ci-buildozer-venv/bin/activate

python -m pip install --upgrade pip "setuptools<70.0.0" wheel
python -m pip install cython==0.29.37 # Pinning to a known stable version
python -m pip install buildozer==1.5.0 # Ensure buildozer itself is installed

git config --global http.version HTTP/1.1 || true
git config --global http.lowSpeedLimit 0 || true
git config --global http.lowSpeedTime 999999 || true
git config --global http.postBuffer 524288000 || true

pushd "$stage_dir" >/dev/null

p4a_parent_dir=".buildozer/android/platform"
p4a_dir="$p4a_parent_dir/python-for-android"
private_app_dir=".buildozer/android/app"
mkdir -p "$p4a_parent_dir"

p4a_ref="${P4A_REF:-$(python3 - <<'PY'
from configparser import ConfigParser
from pathlib import Path

spec = ConfigParser()
spec.read(Path("buildozer.spec"), encoding="utf-8")
for section in ("app", "p4a"):
    if spec.has_option(section, "p4a.branch"):
        print(spec.get(section, "p4a.branch"))
        break
else:
    print("master")
PY
)}"
echo "Using python-for-android ref: $p4a_ref"

p4a_needs_clone=1
if git -C "$p4a_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 && \
   git -C "$p4a_dir" rev-parse --verify HEAD >/dev/null 2>&1; then
  current_p4a_ref="$(git -C "$p4a_dir" describe --tags --exact-match HEAD 2>/dev/null || git -C "$p4a_dir" rev-parse --verify HEAD)"
  if [ "$current_p4a_ref" = "$p4a_ref" ]; then
    p4a_needs_clone=0
  else
    echo "Cached python-for-android ref is $current_p4a_ref; expected $p4a_ref. Refreshing..."
  fi
fi

if [ "$p4a_needs_clone" -eq 1 ]; then
  rm -rf "$p4a_dir"
  echo "Pre-cloning python-for-android ($p4a_ref) with retries..."
  for attempt in 1 2 3 4 5; do
    echo "python-for-android clone attempt $attempt/5"
    if git clone --depth 1 --single-branch --branch "$p4a_ref" https://github.com/kivy/python-for-android.git "$p4a_dir"; then
      git -C "$p4a_dir" describe --tags --exact-match HEAD || git -C "$p4a_dir" rev-parse --short HEAD
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

# Normalize the checkout to a real local branch so Buildozer keeps the patched recipe.
git -C "$p4a_dir" checkout -B "$p4a_ref"

patch_sdl2_image_recipe() {
  python3 - "$p4a_dir" <<'PY'
from pathlib import Path
import sys

recipe = Path(sys.argv[1]) / "pythonforandroid" / "recipes" / "sdl2_image" / "__init__.py"
lines = recipe.read_text(encoding="utf-8").splitlines()
updated = []
skip_prebuild = False

for line in lines:
    if line.strip() == "patches = ['enable-webp.patch']":
        updated.append("    patches = []")
        continue

    if line.startswith("    def prebuild_arch(self, arch):"):
        updated.extend(
            [
                "    def prebuild_arch(self, arch):",
                "        # WebP is disabled to avoid the optional external download step.",
                "        super().prebuild_arch(arch)",
                "",
            ]
        )
        skip_prebuild = True
        continue

    if skip_prebuild:
        if line.startswith("recipe = LibSDL2Image()"):
            skip_prebuild = False
            updated.append(line)
        continue

    updated.append(line)

recipe.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

patch_sdl2_image_recipe

seed_private_app_dir() {
  rm -rf "$private_app_dir"
  mkdir -p "$private_app_dir"
  rsync -a --delete \
    --exclude '.buildozer/' \
    --exclude 'bin/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    ./ "$private_app_dir/"
  if [ ! -f "$private_app_dir/main.py" ]; then
    echo "Private Android app dir is missing main.py after seeding." >&2
    find "$private_app_dir" -maxdepth 2 -type f | sort >&2
    exit 1
  fi
  echo "Seeded Android private app entrypoint:"
  ls -l "$private_app_dir/main.py" "$private_app_dir/app.py" "$private_app_dir/kivy_app.py"
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

python3 - "${artifacts[@]}" <<'PY'
import io
import sys
import tarfile
import zipfile


def has_module(names, module_name):
    suffixes = (f"{module_name}.py", f"{module_name}.pyc")
    return any(name.endswith(suffixes) for name in names)


failures = []
for artifact in sys.argv[1:]:
    try:
        with zipfile.ZipFile(artifact) as apk:
            private_tar = apk.read("assets/private.tar")
        with tarfile.open(fileobj=io.BytesIO(private_tar)) as archive:
            names = set(archive.getnames())
    except Exception as exc:
        failures.append(f"{artifact}: unable to inspect assets/private.tar: {exc}")
        continue

    missing = [module for module in ("main", "kivy_app") if not has_module(names, module)]
    if missing:
        failures.append(f"{artifact}: missing Android app module(s): {', '.join(missing)}")
        continue

    print(f"Verified Android private app modules in {artifact}: main, kivy_app")

if failures:
    print("Android artifact validation failed:", file=sys.stderr)
    for failure in failures:
        print(f" - {failure}", file=sys.stderr)
    sys.exit(1)
PY

cp -f "${artifacts[@]}" "$artifact_dir/"
echo "Android artifacts copied to $artifact_dir:"
for artifact in "${artifacts[@]}"; do
  echo " - $artifact_dir/$(basename "$artifact")"
done
