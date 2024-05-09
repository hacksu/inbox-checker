This is a simple Python discord bot. It comes with a pipenv virtual environment setup. Install pipenv, run `pipenv install` in this directory, switch to the pipenv shell with `pipenv shell`, and run the bot with `python bot.py`.

It requires a file called "private.json" in the root directory that looks like this:

```json
{
    "email_password": "[put password here]",
    "discord_token": "[put discord bot token here]",
    "output_channel": "632635241818882078"
}
```

The password is the one that you would use to log into the HacKSU mailing list normally. The Discord token is the token for a Discord bot account, which you could create [here](https://discord.com/developers/applications). The output channel ID is for the channel where the bot will post its messages. It must be added to the relevant server and have permission to post in the specified channel.
