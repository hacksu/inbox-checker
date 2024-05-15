import asyncio
from datetime import datetime
import json
from urllib.parse import urlencode

import dateutil
import discord

from email_viewer import email_view_server
from config import config
from email_scraper import *


def formatted_current_time():
    return (
        datetime
            .now(tz=dateutil.tz.gettz("US/Eastern"))
            .strftime("%A, %B %d, %Y %I:%M:%S %p %Z")
    )


def get_email_viewer_url(email_url):
    return f"{config["viewer_host"]}/?{urlencode({'email_url': email_url})}"


def get_email_metadata_embed(email_meta, email_url):
    return discord.Embed(
        title=email_meta.subject,
        description=f"*from* {email_meta.from_address}",
        url=get_email_viewer_url(email_url),
        timestamp=email_meta.timestamp
    )


client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    global config

    print(f'We have logged in as {client.user} at {formatted_current_time()}')

    session = login(config["email_password"])
    last_email_url = get_last_email_url(get_recent_email_urls(session))
    last_email_id = email_url_to_id(last_email_url)
    print(f"will alert for emails with IDs greater than {last_email_id}")

    email_meta = get_email_metadata(session, last_email_url)
    discord_embed = get_email_metadata_embed(email_meta, last_email_url)
    await (
        client
            .get_channel(int(config["output_channel"]))
            .send("Email bot is active. Most recent email in inbox is:", embed=discord_embed)
    )

    if "release_notes" in config and len(config["release_notes"]):
        await (
            client
                .get_channel(int(config["output_channel"]))
                .send("Release notes: " + config["release_notes"])
        )

    while True:
        # reload config in case it changed
        with open("private.json", encoding="utf-8") as config_file:
            config = json.load(config_file)
        
        # check for emails newer than the last one observed
        session = login(config["email_password"])
        emails = get_recent_email_urls(session)
        for email_url in emails:
            if email_url_to_id(email_url) > last_email_id:
                email_meta = get_email_metadata(session, email_url)
                discord_embed = get_email_metadata_embed(email_meta, email_url)
                print(f"sending message for email {email_url} at {formatted_current_time()}")
                await (
                    client
                       .get_channel(int(config["output_channel"]))
                       .send("You've got mail!", embed=discord_embed)
                )
        
        # update ID of the last email observed
        new_last_email_id = email_url_to_id(get_last_email_url(emails))
        if new_last_email_id != last_email_id:
            print(f"will now alert for emails with IDs greater than {new_last_email_id}")
            last_email_id = new_last_email_id

        # check again in 3 minutes
        await asyncio.sleep(60 * 3)


async def main():
    email_view_server.listen(8888)
    print("email viewer listening on port 8888")
    print("starting discord bot")
    await asyncio.create_task(client.start(config["discord_token"]))


if __name__ == "__main__":
    # discord.utils.setup_logging(level=logging.DEBUG, root=False)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("exiting due to Ctrl-C")
        exit()
