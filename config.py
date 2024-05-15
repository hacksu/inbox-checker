import json

with open("private.json", encoding="utf-8") as config_file:
    config = json.load(config_file)
    expected_keys = ("discord_token", "email_password", "output_channel", "viewer_host")
    for key in expected_keys:
        assert key in config, f"missing {key} from private.json!"
    allowed_keys = (*expected_keys, "release_notes")
    for key in config:
        assert key in allowed_keys, f"extra key in private.json: {key}"
