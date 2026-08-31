from src.smoke import test_load_and_time, test_new_setup, test_setup_points_limit


def test_config_and_calendar():
    test_load_and_time()


def test_new_setup_play():
    test_new_setup()


def test_setup_points():
    test_setup_points_limit()
