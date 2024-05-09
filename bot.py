import asyncio
import json
from pprint import pprint
import re

import requests
import discord


intents = discord.Intents.default()
client = discord.Client(intents=intents)


with open("private.json", encoding="utf-8") as config_file:
    config = json.load(config_file)
    for key in ("discord_token", "email_password"):
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


@client.event
async def on_ready():

    print(f'We have logged in as {client.user}')

    # >:D
    last_email_id = email_url_to_id(get_last_email_url(get_recent_email_urls(login(config["email_password"]))))

    while True:
        with open("private.json", encoding="utf-8") as config_file:
            config = json.load(config_file)
        
        # NOT TESTED:
        
        emails = get_recent_email_urls(login(config["email_password"]))
        for email in emails:
            if email_url_to_id(email) > last_email_id:
                print("found new email: " + email)
        
        last_email_id = email_url_to_id(get_last_email_url(emails))

        await asyncio.sleep(60)


# client.run(config["discord_token"])

if __name__ == "__main__":
    pprint(get_recent_email_urls(login(config["email_password"])))
