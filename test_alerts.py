import time
import unittest
import unittest.mock as mock

import alerts


class TestAlerts(unittest.TestCase):
    def setUp(self):
        alerts.reset_cooldowns()

    def test_no_alert_above_warning(self):
        result = alerts.check_battery_level("m1", "Mouse", 80, False)
        self.assertIsNone(result)

    def test_warning_alert(self):
        result = alerts.check_battery_level("m1", "Mouse", 20, False)
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "warning")
        self.assertEqual(result["level"], 20)

    def test_critical_alert(self):
        result = alerts.check_battery_level("m1", "Mouse", 10, False)
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "critical")

    def test_below_warning_alert(self):
        result = alerts.check_battery_level("m1", "Mouse", 15, False)
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "warning")

    def test_below_critical_alert(self):
        result = alerts.check_battery_level("m1", "Mouse", 5, False)
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "critical")

    def test_no_alert_when_charging(self):
        result = alerts.check_battery_level("m1", "Mouse", 10, True)
        self.assertIsNone(result)

    def test_cooldown_prevents_repeated_alerts(self):
        alerts.check_battery_level("m1", "Mouse", 10, False)
        result = alerts.check_battery_level("m1", "Mouse", 10, False)
        self.assertIsNone(result)

    def test_cooldown_per_device(self):
        alerts.check_battery_level("m1", "Mouse", 10, False)
        result = alerts.check_battery_level("m2", "Keyboard", 10, False)
        self.assertIsNotNone(result)

    def test_cooldown_expires(self):
        alerts._last_alerts["m1"] = time.time() - alerts.COOLDOWN_SECONDS - 1
        result = alerts.check_battery_level("m1", "Mouse", 10, False)
        self.assertIsNotNone(result)

    @mock.patch("alerts._toaster")
    def test_notification_called(self, mock_toaster):
        alerts.check_battery_level("m1", "Mouse", 10, False)
        mock_toaster.show_toast.assert_called_once()

    @mock.patch("alerts.winsound")
    def test_sound_played_for_critical(self, mock_winsound):
        alerts.check_battery_level("m1", "Mouse", 10, False)
        mock_winsound.MessageBeep.assert_called_once()

    @mock.patch("alerts.winsound")
    def test_no_sound_for_warning(self, mock_winsound):
        alerts.check_battery_level("m1", "Mouse", 20, False)
        mock_winsound.MessageBeep.assert_not_called()

    def test_get_last_alert_time(self):
        self.assertIsNone(alerts.get_last_alert_time("m1"))
        alerts.check_battery_level("m1", "Mouse", 10, False)
        self.assertIsNotNone(alerts.get_last_alert_time("m1"))

    def test_reset_cooldowns(self):
        alerts.check_battery_level("m1", "Mouse", 10, False)
        alerts.reset_cooldowns()
        self.assertIsNone(alerts.get_last_alert_time("m1"))
        result = alerts.check_battery_level("m1", "Mouse", 10, False)
        self.assertIsNotNone(result)

    def test_notification_fallback_to_print(self):
        with mock.patch("alerts._toaster", None):
            with mock.patch("builtins.print") as mock_print:
                alerts.check_battery_level("m1", "Mouse", 10, False)
                mock_print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
