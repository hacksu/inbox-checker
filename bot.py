import asyncio
from datetime import datetime
import json
from urllib.parse import urlencode
import aiohttp

import dateutil
import discord
from slugify import slugify

from email_server import email_view_server
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
        url=get_email_viewer_url(email_url) if email_meta.has_html else email_url,
        timestamp=email_meta.timestamp
    )


async def get_email_image_file(session, email_meta, email_url):
    image = await get_email_image(session, email_url)
    return discord.File(
        image,
        f"email_{slugify(email_meta.subject)}.png"
    )


async def check_mail_forever():
    global config

    async with aiohttp.ClientSession() as webhook_session:

        webhook = discord.Webhook.from_url(config["webhook_url"], session=webhook_session)

        listmail_session = login(config["email_password"])
        last_email_url = get_last_email_url(get_recent_email_urls(listmail_session))
        last_email_id = email_url_to_id(last_email_url)
        print(f"will alert for emails with IDs greater than {last_email_id}")

        email_meta = get_email_metadata(listmail_session, last_email_url)
        discord_embed = get_email_metadata_embed(email_meta, last_email_url)
        await webhook.send(
            "Email bot is active. Most recent email in inbox is:",
            embed = discord_embed,
            file = await get_email_image_file(
                listmail_session, email_meta, last_email_url
            )
        )

        if "release_notes" in config and len(config["release_notes"]):
            await webhook.send("Release notes: " + config["release_notes"])

    while True:

        # reload config in case it changed
        with open("private.json", encoding="utf-8") as config_file:
            config = json.load(config_file)
        
        # check for emails newer than the last one observed
        listmail_session = login(config["email_password"])
        emails = get_recent_email_urls(listmail_session)
        for email_url in emails:
            if email_url_to_id(email_url) > last_email_id:
                email_meta = get_email_metadata(listmail_session, email_url)
                discord_embed = get_email_metadata_embed(email_meta, email_url)
                print(f"sending message for email {email_url} at {formatted_current_time()}")
                async with aiohttp.ClientSession() as webhook_session:
                    webhook = discord.Webhook.from_url(config["webhook_url"], session=webhook_session)
                    await webhook.send(
                        "You've got mail!",
                        embed = discord_embed,
                        file = await get_email_image_file(
                            listmail_session, email_meta, email_url
                        )
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
    print("starting webhook-based discord bot")
    await asyncio.create_task(check_mail_forever())


if __name__ == "__main__":
    # discord.utils.setup_logging(level=logging.DEBUG, root=False)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("exiting due to Ctrl-C")
        exit()
