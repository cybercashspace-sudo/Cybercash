#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_ROOT="${CYBERCASH_BUILD_ROOT:-$HOME/.cybercash_android_build}"
STAGE_DIR="$BUILD_ROOT/source"
VENV_DIR="$BUILD_ROOT/.buildozer-venv"
APK_DEST_DIR="$SOURCE_DIR/bin"
BUILD_LOG="$BUILD_ROOT/buildozer_build.log"

mkdir -p "$BUILD_ROOT"

# Keep a Linux-local log so build progress stays readable even when the repo lives on /mnt/c.
exec > >(tee -a "$BUILD_LOG") 2>&1

APT_GET_OPTS=(-o Acquire::Retries=5 -o Acquire::http::Timeout=120 -o Acquire::https::Timeout=120 -o Acquire::ForceIPv4=true)
REQUIRED_BINS=(git python3 pip3 rsync unzip zip ccache javac)
missing_bins=()

for bin in "${REQUIRED_BINS[@]}"; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        missing_bins+=("$bin")
    fi
done

if [ "${#missing_bins[@]}" -eq 0 ]; then
    echo "Host build tools already present; skipping apt bootstrap."
else
    echo "Missing host tools: ${missing_bins[*]}"
    if [ "$(id -u)" -eq 0 ]; then
        apt_cmd=(apt-get)
    elif [ -n "${WSL_SUDO_PASSWORD:-${SUDO_PASSWORD:-}}" ]; then
        sudo_password="${WSL_SUDO_PASSWORD:-${SUDO_PASSWORD:-}}"
        printf '%s\n' "$sudo_password" | sudo -S -v
        apt_cmd=(sudo -n apt-get)
    elif sudo -n true 2>/dev/null; then
        apt_cmd=(sudo apt-get)
    else
        echo "This script needs root or passwordless sudo for apt."
        echo "Run it from a root WSL shell, or set WSL_SUDO_PASSWORD before retrying."
        exit 1
    fi

    "${apt_cmd[@]}" "${APT_GET_OPTS[@]}" update
    "${apt_cmd[@]}" "${APT_GET_OPTS[@]}" install -y --no-install-recommends ant autoconf automake build-essential ccache git libffi-dev libssl-dev libtool openjdk-17-jdk pkg-config python3-dev python3-pip python3-setuptools python3-venv rsync unzip zip zlib1g-dev
fi

case "$STAGE_DIR" in
    "$BUILD_ROOT"/*) ;;
    *)
        echo "Refusing to stage outside the build root: $STAGE_DIR"
        exit 1
        ;;
esac

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

# Buildozer is much happier when the project lives on the Linux filesystem.
# Copy the Windows-mounted checkout to a staged path under $HOME before building.
rsync -a --delete \
    --exclude '.buildozer' \
    --exclude '.buildozer-venv' \
    --exclude '.git' \
    --exclude '.github' \
    --exclude '.kivy_runtime' \
    --exclude '.venv' \
    --exclude 'Admin_Dashboard' \
    --exclude 'BoG_Submission_Pack' \
    --exclude 'Compliance_Policies' \
    --exclude 'Doc' \
    --exclude 'Lib' \
    --exclude 'Scripts' \
    --exclude 'Tools' \
    --exclude 'build' \
    --exclude 'backend' \
    --exclude 'bin' \
    --exclude 'cyber_cash' \
    --exclude 'dist' \
    --exclude 'frontend' \
    --exclude 'include' \
    --exclude 'libs' \
    --exclude 'node_modules' \
    --exclude 'postgres_local' \
    --exclude 'public' \
    --exclude 'share' \
    --exclude 'tcl' \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '*.db' \
    --exclude '*.dll' \
    --exclude '*.exe' \
    --exclude '*.key' \
    --exclude '*.log' \
    --exclude '*.pdb' \
    --exclude '*.pyc' \
    --exclude 'buildozer_build.log' \
    --exclude 'buildozer_build.pid' \
    --exclude 'LICENSE*' \
    --exclude 'package-lock.json' \
    --exclude 'package.json' \
    --exclude 'README*' \
    --exclude 'session.json' \
    --exclude 'user_data.json' \
    "$SOURCE_DIR"/ "$STAGE_DIR"/

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# GitHub source fetches can stall on WSL; keep Git on HTTP/1.1 and avoid low-speed aborts.
git config --global http.version HTTP/1.1 || true
git config --global http.lowSpeedLimit 0 || true
git config --global http.lowSpeedTime 999999 || true
git config --global http.postBuffer 524288000 || true

PIP_TIMEOUT="${PIP_TIMEOUT:-120}"
PIP_RETRIES="${PIP_RETRIES:-10}"

python -m pip install --upgrade pip setuptools wheel --default-timeout "$PIP_TIMEOUT" --retries "$PIP_RETRIES"
python -m pip install --upgrade "cython<3" buildozer --default-timeout "$PIP_TIMEOUT" --retries "$PIP_RETRIES"

cd "$STAGE_DIR"

P4A_PARENT_DIR="$STAGE_DIR/.buildozer/android/platform"
P4A_DIR="$P4A_PARENT_DIR/python-for-android"
mkdir -p "$P4A_PARENT_DIR"

if ! git -C "$P4A_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
   ! git -C "$P4A_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
    rm -rf "$P4A_DIR"
    echo "Pre-cloning python-for-android with retries..."
    for attempt in 1 2 3 4 5; do
        echo "python-for-android clone attempt $attempt/5"
        if git clone --depth 1 --single-branch --branch master https://github.com/kivy/python-for-android.git "$P4A_DIR"; then
            break
        fi
        rm -rf "$P4A_DIR"
        if [ "$attempt" -eq 5 ]; then
            echo "Failed to pre-clone python-for-android after multiple attempts."
            exit 1
        fi
        sleep $((attempt * 10))
    done
fi

buildozer android debug

mkdir -p "$APK_DEST_DIR"
shopt -s nullglob
apk_files=("$STAGE_DIR"/bin/*.apk)
if [ "${#apk_files[@]}" -eq 0 ]; then
    echo "Build completed, but no APK was found in $STAGE_DIR/bin"
    exit 1
fi

cp -f "${apk_files[@]}" "$APK_DEST_DIR"/
echo "APK copied to:"
for apk_file in "${apk_files[@]}"; do
    echo " - $APK_DEST_DIR/$(basename "$apk_file")"
done
