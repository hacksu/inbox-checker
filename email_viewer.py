from textwrap import dedent
import tornado.web
import tornado.ioloop
import base64

from config import config
from email_scraper import get_email_html, login

class MainHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        auth_header = self.request.headers.get("Authorization")
        if auth_header:
            auth_type, auth_data = auth_header.split()
            if auth_type == "Basic":
                username, password = base64.b64decode(auth_data).decode().split(":")
                if password == config["email_password"]:
                    return username
        return None

    def get(self):
        user = self.get_current_user()
        if user is None:
            return self.request_auth()
        email_url = self.get_query_argument("email_url", default=None)
        if email_url is None:
            self.write("<p>No email URL specified</p>")
        else:
            framed_document = (
                get_email_html(login(config["email_password"]), email_url)
                    .replace("\n", " ")  # i don't think this is technically necessary
                    .replace('"', '&quot;')
            )
            self.write(dedent(f"""
                <!DOCTYPE HTML>
                <html>
                    <body>
                        <iframe sandbox style="width: 100vw; height: 100vh" srcdoc="{framed_document}"></iframe>
                    </body>
                </html>
            """))

    def request_auth(self):
        self.set_header("WWW-Authenticate", 'Basic realm="Authentication Required"')
        self.set_status(401)
        self.finish()


email_view_server = tornado.web.Application([
    (r"/", MainHandler),
])
