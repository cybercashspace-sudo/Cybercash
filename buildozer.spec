[app]
title = CYBER CASH
package.name = cybercash
package.domain = org.cybercash
source.dir = .
source.include_exts = py,kv,json,png,jpg,jpeg,atlas,ttf,otf,mp4
source.exclude_dirs = .buildozer,.buildozer-venv,.git,.github,.kivy_runtime,.venv,.pytest_cache,.qodo,.vscode,build,dist,android_build,node_modules,venv,Lib,Scripts,DLLs,include,libs,Tools,tcl,share,backend,frontend,kivy_frontend,admin-panel,Admin_Dashboard,BoG_Submission_Pack,Compliance_Policies,Doc,postgres_local,public,cyber_cash,__pycache__
source.exclude_patterns = *.log,*.pdb,*.dll,*.exe,*.pyc,*.db,*.env,*.key,package-lock.json,package.json,user_data.json,session.json,start_test.txt,README*,LICENSE*,CYBERCASH_FULL_APP.zip,*/__pycache__/*,__pycache__/*
version = 1.0.0
requirements = python3,kivy,kivymd,requests,python-dotenv
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,USE_BIOMETRIC,USE_FINGERPRINT
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.enable_androidx = True
android.accept_sdk_license = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 0

[python]
python_version = 3
