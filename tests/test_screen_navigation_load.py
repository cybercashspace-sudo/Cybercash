def test_airtime_request_guard_does_not_import_removed_overlay():
    from features.airtime_data.request_guard import RequestGuardMixin

    class _Parent:
        def on_kv_post(self, _widget):
            self.parent_kv_post_called = True

    class _Harness(RequestGuardMixin, _Parent):
        pass

    harness = object.__new__(_Harness)
    RequestGuardMixin.on_kv_post(harness, None)
    assert harness.parent_kv_post_called


def test_admin_dashboard_kv_layout_parses():
    # Importing the module calls Builder.load_string(KV), just as ensure_screen
    # does when the admin opens the dashboard.
    from screens import admin_dashboard

    assert "Agent" + chr(92) + "nApprovals" in admin_dashboard.KV
