import getpass
import os.path
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from requests import HTTPError, Response

HOST = "ais.usvisa-info.com"
DEFAULT_HEADERS = {
    "Host": HOST,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                  "like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36",
    "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", "
                 "\"YaBrowser\";v=\"24.1\", \"Yowser\";v=\"2.5\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "Windows",
}
DOCUMENT_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "ru,en;q=0.9,de;q=0.8,bg;q=0.7",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "no-store",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Upgrade-Insecure-Requests": "1"
}
JSON_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "ru,en;q=0.9,de;q=0.8,bg;q=0.7",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}
X_CSRF_TOKEN_HEADER = "X-CSRF-Token"
COOKIE_HEADER = "Cookie"
COUNTRIES = {
    "ar": "Argentina",
    "ec": "Ecuador",
    "bs": "The Bahamas",
    "gy": "Guyana",
    "bb": "Barbados",
    "jm": "Jamaica",
    "bz": "Belize",
    "mx": "Mexico",
    "br": "Brazil",
    "py": "Paraguay",
    "bo": "Bolivia",
    "pe": "Peru",
    "ca": "Canada",
    "sr": "Suriname",
    "cl": "Chile",
    "tt": "Trinidad and Tobago",
    "co": "Colombia",
    "uy": "Uruguay",
    "cw": "Curacao",
    "us": "United States (Domestic Visa Renewal)",
    "al": "Albania",
    "ie": "Ireland",
    "am": "Armenia",
    "kv": "Kosovo",
    "az": "Azerbaijan",
    "mk": "North Macedonia",
    "be": "Belgium",
    "nl": "The Netherlands",
    "ba": "Bosnia and Herzegovina",
    "pt": "Portugal",
    "hr": "Croatia",
    "rs": "Serbia",
    "cy": "Cyprus",
    "es": "Spain and Andorra",
    "fr": "France",
    "tr": "Turkiye",
    "gr": "Greece",
    "gb": "United Kingdom",
    "it": "Italy",
    "il": "Israel, Jerusalem, The West Bank, and Gaza",
    "ae": "United Arab Emirates",
    "ir": "Iran",
    "ao": "Angola",
    "rw": "Rwanda",
    "cm": "Cameroon",
    "sn": "Senegal",
    "cv": "Cabo Verde",
    "tz": "Tanzania",
    "cd": "The Democratic Republic of the Congo",
    "za": "South Africa",
    "et": "Ethiopia",
    "ug": "Uganda",
    "ke": "Kenya",
    "zm": "Zambia",
}
CONFIG_FILE = "config"
UNAUTHORIZED_STATUS = 401
MAX_ERROR_DELAY_SECONDS = 4 * 60 * 60
HTML_PARSER = "html.parser"


class NoScheduleIdException(Exception):
    def __init__(self):
        super().__init__("No schedule id")


class Logger:
    def __init__(self, debug: bool = True):
        self.debug = debug

    def __call__(self, message: str | Exception, force: bool = False):
        if self.debug or force:
            print(f"[{datetime.now().isoformat()}] {message}")


class Config:
    def __init__(self, path: str):
        self.path = path

        config_data = self.load()

        self.email = config_data.get("EMAIL")
        self.password = config_data.get("PASSWORD")
        self.country = config_data.get("COUNTRY")
        self.facility_id = config_data.get("FACILITY_ID")
        try:
            self.delay_seconds = config_data.get("DELAY_SECONDS")
            self.delay_seconds = int(self.delay_seconds) if self.delay_seconds else None
        except ValueError:
            self.delay_seconds = None
        self.debug = config_data.get("DEBUG")
        self.debug = bool(self.debug) if self.debug else None

    def save(self):
        with open(self.path, "w") as f:
            f.write(
                f"EMAIL={self.email}\nPASSWORD={self.password}\nCOUNTRY={self.country}"
                f"\nDEBUG={self.debug}\nFACILITY_ID={self.facility_id}\nDELAY_SECONDS={self.delay_seconds}"
            )

    def load(self) -> dict:
        config_data = dict()
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                for line in f.readlines():
                    param = line.strip().split("=", maxsplit=1)
                    if len(param) == 2:
                        config_data[param[0].strip()] = param[1].strip()
        return config_data


class Appointment:
    def __init__(self, appointment_date: str, appointment_time: str):
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time


class Bot:
    def __init__(self, config: Config):
        self.logger = Logger(config.debug)
        self.config = config
        self.url = f"https://{HOST}/en-{config.country}/niv"

        self.headers: Optional[dict] = None
        self.appointment_datetime: Optional[datetime] = None
        self.schedule_id: Optional[str] = None

    def init(self):
        self.login()
        self.init_current_data()
        self.init_csrf_and_cookie()

    def login(self):
        self.logger("Get sign in")
        response = requests.get(
            f"{self.url}/users/sign_in",
            headers={
                COOKIE_HEADER: "",
                "Referer": f"{self.url}/users/sign_in",
                **DOCUMENT_HEADERS
            }
        )
        response.raise_for_status()

        cookies = response.headers.get("set-cookie")

        soup = BeautifulSoup(response.text, HTML_PARSER)
        csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]

        self.logger("Post sing in")
        response = requests.post(
            f"{self.url}/users/sign_in",
            headers={
                **DEFAULT_HEADERS,
                X_CSRF_TOKEN_HEADER: csrf_token,
                COOKIE_HEADER: cookies,
                "Accept": "*/*;q=0.5, text/javascript, application/javascript, application/ecmascript, "
                          "application/x-ecmascript",
                "Referer": f"{self.url}/users/sign_in",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            },
            data=urlencode({
                "user[email]": self.config.email,
                "user[password]": self.config.password,
                "policy_confirmed": "1",
                "commit": "Sign In"
            })
        )
        response.raise_for_status()

        self.headers = {COOKIE_HEADER: response.headers.get("set-cookie")}

    def init_current_data(self):
        self.logger("Get current appointment")
        response = requests.get(
            self.url,
            headers={
                **self.headers,
                **DOCUMENT_HEADERS
            }
        )
        response.raise_for_status()

        match = re.search(
            rf"href=\"/en-{self.config.country}/niv/schedule/(\d+)/continue_actions\">Continue</a>",
            response.text
        )
        if not match:
            raise NoScheduleIdException()
        self.schedule_id = match.group(1)

        match = re.search(r"\d{1,2} \w+?, \d{4}, \d{1,2}:\d{1,2}", response.text)
        if match:
            self.appointment_datetime = datetime.strptime(match.group(0), "%d %B, %Y, %H:%M")

    def init_csrf_and_cookie(self):
        self.logger("Init csrf")
        response = self.load_change_appointment_page()
        csrf = BeautifulSoup(response.text, HTML_PARSER).find("meta", {"name": "csrf-token"})["content"]
        self.headers = {
            COOKIE_HEADER: response.headers.get("set-cookie"),
            X_CSRF_TOKEN_HEADER: csrf
        }

    def get_available_facility_id(self):
        self.logger("Get facility id list")
        locations = (BeautifulSoup(self.load_change_appointment_page().text, HTML_PARSER)
                     .find("select", {"id": "appointments_consulate_appointment_facility_id"})
                     .findAll("option"))
        facility_id_to_location = dict()
        for location in locations:
            if location["value"]:
                facility_id_to_location[location["value"]] = location.text
        return facility_id_to_location

    def load_change_appointment_page(self) -> Response:
        self.logger("Get new appointment")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment",
            headers={
                **self.headers,
                "Sec-Fetch-User": "?1",
                "Referer": f"{self.url}/schedule/{self.schedule_id}/continue_actions",
                **DOCUMENT_HEADERS
            }
        )
        response.raise_for_status()
        return response

    def get_available_appointment(self) -> Optional[Appointment]:
        self.logger("Get available date")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/days/"
            f"{self.config.facility_id}.json?appointments[expedite]=false",
            headers={
                **self.headers,
                **JSON_HEADERS,
                "Referer": f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()

        data = response.json()
        available_date = data[0]["date"] if len(data) > 0 else None

        if not available_date:
            return None

        self.logger("Get available time")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/times/{self.config.facility_id}.json?"
            f"date={available_date}&appointments[expedite]=false",
            headers={
                **self.headers,
                **JSON_HEADERS,
                "Referer": f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()

        data = response.json()
        available_time = data["business_times"][0] or data["available_times"][0]

        if not available_time:
            return None

        return Appointment(available_date, available_time)

    def book(self, appointment: Appointment):
        self.logger(
            "=====================\n"
            "#                   #\n"
            "#                   #\n"
            "#    Try to book    #\n"
            "#                   #\n"
            "#                   #\n"
            f"# {appointment.appointment_time}  {appointment.appointment_date} #\n"
            "#                   #\n"
            "#                   #\n"
            "=====================",
            True
        )

        response = requests.post(
            f"{self.url}/schedule/{self.schedule_id}/appointment",
            headers={
                **self.headers,
                **DOCUMENT_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-store",
                "Sec-Fetch-User": "?1",
                "Origin": f"https://{HOST}",
                "Referer": f"{self.url}/schedule/{self.schedule_id}/appointment"
            },
            data=urlencode({
                "authenticity_token": self.headers[X_CSRF_TOKEN_HEADER],
                "confirmed_limit_message": "1",
                "use_consulate_appointment_capacity": "true",
                "appointments[consulate_appointment][facility_id]": self.config.facility_id,
                "appointments[consulate_appointment][date]": appointment.appointment_date,
                "appointments[consulate_appointment][time]": appointment.appointment_time
            })
        )
        response.raise_for_status()

        self.logger(
            "=====================\n"
            "#                   #\n"
            "#                   #\n"
            "#     Booked at     #\n"
            "#                   #\n"
            "#                   #\n"
            f"# {appointment.appointment_time}  {appointment.appointment_date} #\n"
            "#                   #\n"
            "#                   #\n"
            "#  Close window to  #\n"
            "#    end awaiting   #\n"
            "=====================",
            True
        )

    def process(self):
        appointment = self.get_available_appointment()
        if not appointment:
            self.logger("No available date")
            return False

        available_datetime = datetime.strptime(
            appointment.appointment_time + " " + appointment.appointment_date,
            "%H:%M %Y-%m-%d"
        )
        self.logger(f"Nearest: {appointment.appointment_time} {appointment.appointment_date}")
        if self.appointment_datetime and self.appointment_datetime <= available_datetime:
            return False

        self.book(appointment)
        self.appointment_datetime = available_datetime
        return True


def main():
    config = Config(CONFIG_FILE)

    while not config.delay_seconds:
        try:
            config.delay_seconds = int(input("Delay seconds: "))
        except ValueError:
            config.delay_seconds = None
    if not config.email:
        config.email = input("Enter email: ")
    if not config.password:
        config.password = getpass.getpass("Enter password: ")
    while not config.country:
        country = input(
            "Select country (enter two letters) \n" + "\n".join(
                [key + " " + value for (key, value) in COUNTRIES.items()]) + "\n"
        )
        if country in COUNTRIES:
            config.country = country
    if not config.debug:
        config.debug = input("Do you want to see all logs (Y/N)?: ").upper() == "Y"

    if not config.facility_id:
        bot = Bot(config)
        bot.init()

        locations = bot.get_available_facility_id()
        if len(locations) == 1:
            config.facility_id = next(iter(locations))
        else:
            facility_id = None
            while not facility_id:
                facility_id = input(
                    "Choose city (enter number) \n" +
                    "\n".join([x[0] + "  " + x[1] for x in locations.items()])
                ) + "\n"
                if facility_id not in locations:
                    facility_id = None
            config.facility_id = facility_id

    config.save()

    bot = Bot(config)
    logger = Logger(config.debug)
    errors_count = 0

    reinit = True
    while True:
        try:
            if reinit:
                bot.init()
                reinit = False

            bot.process()

            errors_count = max(0, errors_count - 1)
        except Exception as err:
            logger(err)

            if isinstance(err, HTTPError) and err.response.status_code == UNAUTHORIZED_STATUS:
                reinit = True
            else:
                errors_count += 1

        time.sleep(config.delay_seconds + min(MAX_ERROR_DELAY_SECONDS, errors_count * config.delay_seconds))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
