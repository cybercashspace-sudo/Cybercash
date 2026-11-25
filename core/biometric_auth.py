"""Android fingerprint capability checks and authentication bridge."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Callable

from kivy.utils import platform

logger = logging.getLogger(__name__)


class FingerprintAuthenticator:
    """Own the Java callback and cancellation signal for one fingerprint prompt."""

    def __init__(self) -> None:
        self._manager = None
        self._cancellation = None
        self._callback = None
        self._runnable = None
        self._activity = None
        self._on_success: Callable[[], None] | None = None
        self._on_error: Callable[[str], None] | None = None
        self._on_failed: Callable[[], None] | None = None
        self._settled = False
        self._lock = Lock()

    @staticmethod
    def _fingerprint_manager():
        if str(platform or "").lower() != "android":
            return None, None

        from jnius import autoclass, cast

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        context = autoclass("android.content.Context")
        manager = cast(
            "android.hardware.fingerprint.FingerprintManager",
            activity.getSystemService(context.FINGERPRINT_SERVICE),
        )
        return activity, manager

    @classmethod
    def is_available(cls) -> bool:
        """Return true only when Android fingerprint hardware has an enrolled print."""
        try:
            _activity, manager = cls._fingerprint_manager()
            return bool(
                manager is not None
                and manager.isHardwareDetected()
                and manager.hasEnrolledFingerprints()
            )
        except Exception:
            return False

    def authenticate(
        self,
        *,
        on_success: Callable[[], None],
        on_error: Callable[[str], None],
        on_failed: Callable[[], None] | None = None,
    ) -> bool:
        """Start one Android fingerprint scan, retaining JNI objects until completion."""
        if str(platform or "").lower() != "android":
            try:
                on_error("Fingerprint unlock is available in the Android app.")
            except Exception:
                logger.exception("Fingerprint availability callback failed")
            return False

        try:
            from jnius import PythonJavaClass, autoclass, java_method

            activity, manager = self._fingerprint_manager()
            if (
                manager is None
                or not manager.isHardwareDetected()
                or not manager.hasEnrolledFingerprints()
            ):
                on_error("Set up a fingerprint on this device, then sign in with your PIN.")
                return False

            owner = self

            class AuthenticationCallback(PythonJavaClass):
                __javainterfaces__ = [
                    "android/hardware/fingerprint/FingerprintManager$AuthenticationCallback"
                ]
                __javacontext__ = "app"

                @java_method(
                    "(Landroid/hardware/fingerprint/FingerprintManager$AuthenticationResult;)V"
                )
                def onAuthenticationSucceeded(self, _result):
                    owner._complete(success=True)

                @java_method("(ILjava/lang/CharSequence;)V")
                def onAuthenticationError(self, _code, message):
                    owner._complete(
                        success=False,
                        message=str(message or "Fingerprint check was not completed."),
                    )

                @java_method("()V")
                def onAuthenticationFailed(self):
                    owner._notify_failed()

            class AuthenticateRunnable(PythonJavaClass):
                __javainterfaces__ = ["java/lang/Runnable"]
                __javacontext__ = "app"

                @java_method("()V")
                def run(self):
                    try:
                        manager.authenticate(None, cancellation, 0, callback, None)
                    except Exception as exc:
                        logger.warning(
                            "Android fingerprint request failed (error_type=%s)",
                            type(exc).__name__,
                        )
                        owner._complete(
                            success=False,
                            message="Fingerprint unlock is unavailable right now. Sign in with your PIN.",
                        )

            cancellation = autoclass("android.os.CancellationSignal")()
            callback = AuthenticationCallback()
            runnable = AuthenticateRunnable()
            self._activity = activity
            self._manager = manager
            self._cancellation = cancellation
            self._callback = callback
            self._runnable = runnable
            self._on_success = on_success
            self._on_error = on_error
            self._on_failed = on_failed

            activity.runOnUiThread(runnable)
            return True
        except Exception as exc:
            logger.warning(
                "Android fingerprint prompt could not be started (error_type=%s)",
                type(exc).__name__,
            )
            self._complete(
                success=False,
                message="Fingerprint unlock is unavailable right now. Sign in with your PIN.",
            )
            return False

    def cancel(self) -> None:
        cancellation = self._cancellation
        if cancellation is None:
            return
        try:
            cancellation.cancel()
        except Exception:
            pass

    def release(self) -> None:
        """Drop strong references once Android reports that the prompt has ended."""
        self._manager = None
        self._cancellation = None
        self._callback = None
        self._runnable = None
        self._activity = None
        self._on_success = None
        self._on_error = None
        self._on_failed = None

    def _complete(self, *, success: bool, message: str = "") -> None:
        with self._lock:
            if self._settled:
                return
            self._settled = True
            callback = self._on_success if success else self._on_error

        if callback is None:
            return
        try:
            if success:
                callback()
            else:
                callback(message)
        except Exception:
            logger.exception("Fingerprint result callback failed")

    def _notify_failed(self) -> None:
        with self._lock:
            if self._settled:
                return
            callback = self._on_failed
        if callback is not None:
            try:
                callback()
            except Exception:
                logger.exception("Fingerprint retry callback failed")
