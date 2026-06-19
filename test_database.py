import os
import tempfile
import time
import unittest
import database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_db_file = database.DB_FILE
        database.DB_FILE = os.path.join(self.temp_dir, "test.db")
        database._connection = None
        database.init_db()

    def tearDown(self):
        database.close_db()
        database.DB_FILE = self.orig_db_file
        if os.path.exists(database.DB_FILE):
            os.remove(database.DB_FILE)
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)

    def test_init_db_creates_table(self):
        result = database._get_connection().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='battery_history'"
        ).fetchone()
        self.assertIsNotNone(result)

    def test_save_and_get_latest(self):
        database.save_battery("mouse1", "Rival 3", 85, False)
        result = database.get_latest("mouse1")
        self.assertIsNotNone(result)
        self.assertEqual(result["device_id"], "mouse1")
        self.assertEqual(result["device_name"], "Rival 3")
        self.assertEqual(result["level"], 85)
        self.assertEqual(result["is_charging"], 0)

    def test_save_battery_charging(self):
        database.save_battery("mouse1", "Rival 3", 50, True)
        result = database.get_latest("mouse1")
        self.assertEqual(result["is_charging"], 1)

    def test_get_history(self):
        t = time.time()
        database.save_battery("mouse1", "Rival 3", 80, False, t - 10)
        database.save_battery("mouse1", "Rival 3", 75, False, t - 5)
        database.save_battery("mouse1", "Rival 3", 70, False, t)
        history = database.get_history("mouse1")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["level"], 70)
        self.assertEqual(history[2]["level"], 80)

    def test_get_history_time_range(self):
        t = time.time()
        database.save_battery("mouse1", "Rival 3", 80, False, t - 100)
        database.save_battery("mouse1", "Rival 3", 75, False, t - 50)
        database.save_battery("mouse1", "Rival 3", 70, False, t)
        history = database.get_history("mouse1", start_time=t - 60, end_time=t - 10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["level"], 75)

    def test_get_devices(self):
        database.save_battery("mouse1", "Rival 3", 80, False)
        database.save_battery("mouse2", "Sensei Ten", 90, True)
        devices = database.get_devices()
        self.assertEqual(len(devices), 2)
        device_ids = {d["device_id"] for d in devices}
        self.assertEqual(device_ids, {"mouse1", "mouse2"})

    def test_get_latest_no_data(self):
        result = database.get_latest("nonexistent")
        self.assertIsNone(result)

    def test_get_history_limit(self):
        t = time.time()
        for i in range(5):
            database.save_battery("mouse1", "Rival 3", 50 + i, False, t + i)
        history = database.get_history("mouse1", limit=3)
        self.assertEqual(len(history), 3)

    def test_multiple_devices_same_timestamp(self):
        t = time.time()
        database.save_battery("mouse1", "Rival 3", 80, False, t)
        database.save_battery("mouse2", "Sensei Ten", 90, True, t)
        latest = database.get_latest()
        self.assertIn(latest["device_id"], ["mouse1", "mouse2"])


if __name__ == "__main__":
    unittest.main()
