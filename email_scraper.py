from html import unescape
import requests
import re
from itertools import islice
from typing import NamedTuple
from datetime import datetime
import dateutil

from html2text import HTML2Text
from dateutil.parser import parse as parse_date


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
    [("subject", str), ("from_address", str), ("timestamp", datetime), ("has_html", bool)]
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
        ),
        get_email_html(session, email_url) is not None
    )


def get_email_html(session: requests.Session, email_url: str) -> str | None:
    """
        This grabs the HTML "attachment" from Mailman that contains the actual
        rich text content of the email.
    """
    email = session.get(email_url).text
    # this is where my valiant attempt to avoid hardcoding too much information,
    # like the name of the mailing list, in the url patterns breaks down
    html_url_pattern = r"https://listmail.cs.kent.edu/mailman/private/hacksu/attachments/\d+/\w+/attachment(?:-0001)?.htm"
    match = re.search(html_url_pattern, email)
    if match:
        html_email_page = session.get(match.group(0)).text
        html_email_body = re.search(r"<tt>(.*)</tt>", html_email_page, flags=re.DOTALL).group(1)
        return HTML2Text().handle(html_email_body)
    else:
        return None
