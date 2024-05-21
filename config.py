import json

def load_config():
    with open("private.json", encoding="utf-8") as config_file:
        config = json.load(config_file)
        expected_keys = ("email_password", "webhook_url", "viewer_host")
        for key in expected_keys:
            assert key in config, f"missing {key} from private.json!"
        allowed_keys = (*expected_keys, "release_notes")
        for key in config:
            assert key in allowed_keys, f"extra key in private.json: {key}"
        return config
