from configparser import ConfigParser

config_object = ConfigParser()

config_object["BOT_INFO"] = {
    "game": "you.",
    "message_lockout_time": "10",
    "admin_txt_channel_id": "400449730372567040",
    "silenced_voice_channel_id": "272798086873612289",
    "auto_lock": 0
}

config_object["USER_INFO"] = {
    "silencedId": "432649125327142925,271834336884424705",
    "silencedNick": "Bound and Gagged"
}

with open('config.ini', 'w') as conf:
    config_object.write(conf)
