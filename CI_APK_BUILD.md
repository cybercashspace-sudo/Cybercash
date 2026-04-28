# CI APK Build

This repository uses GitHub Actions on Ubuntu 22.04 as the supported Android build path.

## Why this path

- The app is packaged against `https://cybercash.space`.
- The workflow pins Python `3.11` and `Cython<3` to avoid the `pyjnius` compile failure seen in WSL.
- The workflow stages a clean Android source tree before building, so the tracked Windows Python runtime does not contaminate the APK job.
- The workflow runs on Linux directly, so it avoids the Windows WSL and local Python runtime issues.

## Build APK

1. Push the repo to GitHub.
2. Open **Actions**.
3. Run **Build Android APK**.
4. Download the `cybercash-android-apk` artifact from the run summary.

## Publish release

1. Push a tag like `v1.0.0`, or run **Publish Android Release** manually with a tag name.
2. GitHub Actions will build the APK and attach it to the GitHub release.
