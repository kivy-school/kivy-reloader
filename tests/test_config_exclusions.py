from kivy_reloader.config import Config


def test_project_dist_is_builtin_phone_deployment_exclusion():
    config = Config.__new__(Config)
    config.config = {}

    assert 'project_dist' in config.FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE
