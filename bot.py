import asyncio
from typing import NamedTuple
from datetime import datetime
from itertools import islice
import json
import re

import dateutil
from html2text import HTML2Text
import requests
import discord
from dateutil.parser import parse as parse_date


with open("private.json", encoding="utf-8") as config_file:
    config = json.load(config_file)
    for key in ("discord_token", "email_password", "output_channel"):
        assert key in config, f"missing {key} from private.json!"


def login(password: str, list_name: str = "hacksu") -> requests.Session:
    "This function creates a login session that can be used for later requests"
    
    session = requests.Session()
        
    login_url = f"https://listmail.cs.kent.edu/mailman/admin/{list_name}"
    
    session.post(login_url, { "adminpw": password }).raise_for_status()

    return session


def get_recent_email_urls(session: requests.Session, list_name: str = "hacksu") -> list[str]:
    """
    This function retrieves the URLs corresponding to the emails that have
    arrived in the previous two calendar months.

    It uses the most recent two calendar months instead of just the most recent
    calendar month to avoid missing e.g. an email that arrives in the last
    second of January when performing the first check in February.
    """

    base_url = f"https://listmail.cs.kent.edu/mailman/private/{list_name}/"

    # find the (relative) urls for the "threads" (each thread is a month of emails)
    archives_request = session.get(base_url)
    threads = list(re.finditer(r'href="(.+?/)thread.html"', archives_request.text, re.IGNORECASE))

    emails = []

    # find the (relative) urls for the emails in the first two threads and
    # concatenate them with the list's base url and the thread's base url
    for thread in threads[:2]:
        thread_request = session.get(base_url + thread.group(1))
        emails += [
            (base_url + thread.group(1) + match.group(1))
            for match in re.finditer(r'href="(\d+.html)"', thread_request.text, re.IGNORECASE)
        ]
    
    return emails


def email_url_to_id(url: str) -> int:
    return int(re.search(r"(\d+).html", url).group(1))


def get_last_email_url(emails: list[str]) -> str:
    "Returns the URL of the email with the highest numerical ID."

    assert len(emails) > 0, "can't get last email of 0 emails"

    return sorted(emails, key=email_url_to_id)[-1]


def deduplicate_string(string: str) -> str:
    """
    When there's no named sender for an email, the mailing list interface just
    shows the "from" address twice, which is annoying. This function will make
    sure a string isn't the same thing twice with a space in the middle.
    """
    if len(string) % 2 == 1 and string[:len(string)//2] == string[len(string)//2+1:]:
        return string[:len(string)//2]
    return string


EmailMetadata = NamedTuple(
    "EmailMetadata",
    [("subject", str), ("from_address", str), ("timestamp", datetime)]
)

def get_email_metadata(session: requests.Session, email_url: str) -> EmailMetadata:
    """
        This attempts to parse the somewhat messy HTML on the email page and
        returns basic information about the email.
    """
    email = session.get(email_url).text
    
    # convert email page to formatted text
    parser = HTML2Text()
    parser.ignore_links = True
    parser.ignore_mailto_links = True
    parser.body_width = 1000000  # keep it from wrapping long lines
    text = parser.handle(email)

    # once we have the email page as formatted text, the subject, "from"
    # address, and timestamp are on the first three lines of the result
    meta = list(islice(
        (l.replace("[Hacksu]", "").strip("#\n _")
            for l in text.splitlines() if len(l.strip())),
        3
    ))
    return EmailMetadata(
        meta[0],
        deduplicate_string(meta[1]),
        parse_date(
            meta[2],
            # need to tell it what EDT and EST mean
            tzinfos={
                "EDT": dateutil.tz.gettz("US/Eastern"),
                "EST": dateutil.tz.gettz("US/Eastern")
            }
        )
    )


def formatted_current_time():
    return (
        datetime
            .now(tz=dateutil.tz.gettz("US/Eastern"))
            .strftime("%A, %B %d, %Y %I:%M:%S %p %Z")
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
    discord_embed = discord.Embed(
        title=email_meta.subject,
        description=f"from {email_meta.from_address}",
        url=last_email_url,
        timestamp=email_meta.timestamp
    )
    await (
        client
            .get_channel(int(config["output_channel"]))
            .send("Email bot is active. Most recent email in inbox is:", embed=discord_embed)
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
                discord_embed = discord.Embed(
                    title=email_meta.subject,
                    description=f"*from* {email_meta.from_address}",
                    url=email_url,
                    timestamp=email_meta.timestamp
                )
                print(f"sending message for email {email_url} at {formatted_current_time()}")
                await (
                    client
                       .get_channel(int(config["output_channel"]))
                       .send("You have mail!", embed=discord_embed)
                )
        
        # update ID of the last email observed
        new_last_email_id = email_url_to_id(get_last_email_url(emails))
        if new_last_email_id != last_email_id:
            print(f"will now alert for emails with IDs greater than {new_last_email_id}")
            last_email_id = new_last_email_id

        # check again in 3 minutes
        await asyncio.sleep(60 * 3)


if __name__ == "__main__":
    client.run(config["discord_token"])
