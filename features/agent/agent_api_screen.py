from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDRaisedButton, MDTextButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from core.navigation import navigate
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.popup_manager import show_backend_result_popup, show_confirm_dialog
from core.responsive_screen import ResponsiveScreen
from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_api_screen.kv")))


class AgentApiScreen(ResponsiveScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self._api_keys_busy = False
        self._screen_active = False
        self._selected_mode = "test"
        self._created_public_label = ""

    def on_enter(self, *_args):
        self._screen_active = True
        self.select_api_mode(self._selected_mode)
        self.load_api_keys()

    def on_leave(self, *_args):
        self._screen_active = False
        self._clear_api_secret()
        self._created_public_label = ""
        parent = getattr(super(), "on_leave", None)
        if callable(parent):
            return parent(*_args)

    def go_back(self):
        return super().go_back()

    def pull_to_refresh(self):
        self.load_api_keys()

    def load_api_keys(self):
        if self._api_keys_busy:
            return
        self._start_api_worker("list", None)

    def generate_api_key(self):
        if self._api_keys_busy:
            return
        name = str(self.ids.api_key_name.text or "").strip()
        if len(name) < 2:
            show_backend_result_popup(self, "Enter a name with at least 2 characters for this API key.", title="Key name needed")
            return
        self.ids.api_key_secret.text = ""
        self.ids.copy_api_key_button.disabled = True
        self.ids.api_key_status.text = "Generating a secure key…"
        self._start_api_worker("create", (name, self._selected_mode))

    def select_api_mode(self, mode: str):
        if mode not in {"test", "live"} or self._api_keys_busy:
            return
        self._selected_mode = mode
        self.ids.test_mode_button.md_bg_color = (0.48, 0.34, 0.06, 1) if mode == "test" else (0.14, 0.15, 0.17, 1)
        self.ids.live_mode_button.md_bg_color = (0.48, 0.34, 0.06, 1) if mode == "live" else (0.14, 0.15, 0.17, 1)

    def revoke_api_key(self, key_id: int):
        if self._api_keys_busy:
            return
        show_confirm_dialog(
            self,
            title="Revoke API key?",
            message="Apps using this key will stop creating new customer checkouts. This cannot be undone.",
            confirm_label="Revoke key",
            on_confirm=lambda: self._start_api_worker("revoke", int(key_id)),
        )

    def _start_api_worker(self, action: str, value):
        if self._api_keys_busy:
            return
        self._api_keys_busy = True
        self.ids.generate_api_key_button.disabled = True
        self.ids.api_key_status.text = {
            "list": "Loading API keys…",
            "create": "Generating a secure key…",
            "revoke": "Revoking API key…",
        }.get(action, "Updating API access…")
        try:
            Thread(target=self._api_keys_worker, args=(action, value), daemon=True).start()
        except Exception:
            self._api_key_error()

    def _api_keys_worker(self, action: str, value):
        try:
            if action == "list":
                result = self.controller.api_keys()
            elif action == "create":
                name, mode = value
                result = self.controller.create_api_key(str(name), str(mode))
            else:
                result = self.controller.revoke_api_key(int(value))
            Clock.schedule_once(lambda _dt, a=action, data=result: self._apply_api_key_result(a, data))
        except Exception as exc:
            message = self._friendly_api_error(exc)
            Clock.schedule_once(lambda _dt, msg=message: self._api_key_error(msg))

    @staticmethod
    def _friendly_api_error(exc: Exception) -> str:
        """Show a safe, actionable server message without exposing internals."""
        response = getattr(exc, "response", None)
        payload = getattr(response, "data", None)
        if payload is None and response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = None
        if payload is not None:
            return extract_backend_message(
                payload,
                fallback="API access could not be updated. Please try again.",
            )
        return sanitize_backend_message(
            exc,
            fallback="API access could not be updated. Check your connection and try again.",
        )

    def _apply_api_key_result(self, action: str, result):
        self._api_keys_busy = False
        self.ids.generate_api_key_button.disabled = False
        if not self._screen_active:
            if action == "create" and isinstance(result, dict) and result.get("id"):
                Thread(target=self._discard_unshown_key, args=(int(result["id"]),), daemon=True).start()
            return
        payload = result if isinstance(result, dict) else {}
        if action == "list":
            self._render_api_keys(payload)
            return
        if action == "create":
            secret = str(payload.get("api_key") or "").strip()
            if not secret:
                self._api_key_error("The API key was not returned. Please try again.")
                return
            self.ids.api_key_secret.text = secret
            self.ids.copy_api_key_button.disabled = False
            mode = str(payload.get("mode") or "live").upper()
            public_key = str(payload.get("public_key") or "")
            self._created_public_label = f"{mode} secret created. Copy it now. Public ID: {public_key}"
            self.ids.api_key_status.text = self._created_public_label
            self.load_api_keys()
            return
        self._clear_api_secret()
        self.ids.api_key_status.text = str(payload.get("message") or "API key revoked.")
        self.load_api_keys()

    def _discard_unshown_key(self, key_id: int):
        try:
            self.controller.revoke_api_key(key_id)
        except Exception:
            pass

    def _render_api_keys(self, payload):
        container = self.ids.api_keys_list
        container.clear_widgets()
        rows = payload.get("items", [])
        active_count = 0
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            revoked = bool(row.get("revoked"))
            if not revoked:
                active_count += 1
            item = MDBoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None, height=dp(62))
            top = MDBoxLayout(orientation="horizontal", spacing=dp(4), size_hint_y=None, height=dp(34))
            top.add_widget(MDLabel(
                text=f"{row.get('name', 'API key')} · {str(row.get('mode') or 'live').upper()} · {'Revoked' if revoked else 'Active'}",
                shorten=True,
                theme_text_color="Secondary",
            ))
            public_key = str(row.get("public_key") or "")
            if public_key:
                top.add_widget(MDTextButton(
                    text="Copy ID",
                    size_hint_x=None,
                    width=dp(68),
                    on_release=lambda _btn, value=public_key: self.copy_public_key(value),
                ))
            if not revoked:
                top.add_widget(MDRaisedButton(
                    text="Revoke",
                    size_hint_x=None,
                    width=dp(82),
                    on_release=lambda _btn, kid=row.get("id"): self.revoke_api_key(int(kid)),
                ))
            item.add_widget(top)
            item.add_widget(MDLabel(
                text=f"Public ID: {public_key}" if public_key else "Public ID unavailable",
                shorten=True,
                theme_text_color="Secondary",
                font_size=dp(11),
            ))
            container.add_widget(item)
        if self.ids.api_key_secret.text:
            self.ids.api_key_status.text = self._created_public_label or "Key created. Copy it now; it will not be shown again."
        elif active_count == 0:
            self.ids.api_key_status.text = "No active API keys yet. Create one to get started."
        else:
            self.ids.api_key_status.text = f"{active_count} active key(s). Secret values cannot be viewed again."

    def _api_key_error(self, message: str = "API access could not be updated. Check your connection and try again."):
        self._api_keys_busy = False
        if "generate_api_key_button" in self.ids:
            self.ids.generate_api_key_button.disabled = False
        if "api_key_status" in self.ids:
            self.ids.api_key_status.text = "API key request did not complete."
        if self._screen_active:
            show_backend_result_popup(self, message, title="API access")

    def copy_api_key(self):
        secret = str(self.ids.api_key_secret.text or "").strip()
        if not secret:
            return
        Clipboard.copy(secret)
        self.ids.api_key_status.text = "Key copied. Store it securely; it cannot be viewed again."

    def copy_public_key(self, value: str):
        public_key = str(value or "").strip()
        if public_key.startswith("cc_pub_"):
            Clipboard.copy(public_key)
            self.ids.api_key_status.text = "Public ID copied. It cannot authenticate API requests."

    def _clear_api_secret(self):
        if "api_key_secret" in self.ids:
            self.ids.api_key_secret.text = ""
        if "copy_api_key_button" in self.ids:
            self.ids.copy_api_key_button.disabled = True

    def _go_to_screen(self, screen_name: str):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            return bool(app.go_to_screen(screen_name, fallback="agent_api", transition_style="fade"))
        if self.manager and self.manager.has_screen(screen_name):
            return bool(navigate(self.manager, screen_name, fallback="agent_api", transition_style="fade"))
        return False
