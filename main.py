import os.path
import os.path
import re
import time
import traceback
from datetime import datetime
from typing import Optional, Any, Callable
from urllib.parse import urlencode

import requests
import urllib3
from bs4 import BeautifulSoup
from requests import Response

HOST = "ais.usvisa-info.com"
REFERER = "Referer"
ACCEPT = "Accept"
SET_COOKIE = "set-cookie"
CONTENT_TYPE = "Content-Type"
CACHE_CONTROL_HEADERS = {
    "Cache-Control": "no-store"
}
DEFAULT_HEADERS = {
    "Host": HOST,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                  "like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36",
    "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", "
                 "\"YaBrowser\";v=\"24.1\", \"Yowser\";v=\"2.5\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "Windows",
}
SEC_FETCH_USER_HEADERS = {
    "Sec-Fetch-User": "?1"
}
DOCUMENT_HEADERS = {
    **DEFAULT_HEADERS,
    **CACHE_CONTROL_HEADERS,
    ACCEPT: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "ru,en;q=0.9,de;q=0.8,bg;q=0.7",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Upgrade-Insecure-Requests": "1"
}
JSON_HEADERS = {
    **DEFAULT_HEADERS,
    ACCEPT: "application/json, text/javascript, */*; q=0.01",
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
DATE_TIME_FORMAT = "%H:%M %Y-%m-%d"
DATE_FORMAT = "%d.%m.%Y"
ERROR_START_STATUS = 400
UNAUTHORIZED_STATUS = 401
TRUE = "True"
HTML_PARSER = "html.parser"
PING_DELAY = 2 * 60

CONFIG_FILE = "config"
PROXY_FILE = "proxy"
TIMEOUT = 4
MAX_ERROR_DELAY = 4 * 60 * 60


class NoScheduleIdException(Exception):
    def __init__(self):
        super().__init__("No schedule id")


class UseMainBotException(Exception):
    pass


class Logger:
    def __init__(self, debug: bool = True):
        self.debug = debug

    def __call__(self, message: str | Exception, force: bool = False):
        if self.debug or force:
            print(f"[{datetime.now().isoformat()}] {message}")
            if isinstance(message, Exception):
                traceback.print_exc()


class Config:
    def __init__(self, config_path: str, proxy_path: str):
        self.config_path = config_path

        config_data = dict()
        if not os.path.exists(self.config_path):
            os.mknod(self.config_path)
        with open(self.config_path, "r") as f:
            for line in f.readlines():
                param = line.strip().split("=", maxsplit=1)
                if len(param) == 2:
                    config_data[param[0].strip()] = param[1].strip()

        email = config_data.get("EMAIL")
        if not email:
            email = input("Enter email: ")
        self.email: str = email

        password = config_data.get("PASSWORD")
        if not password:
            password = input("Enter password: ")
        self.password: str = password

        country = config_data.get("COUNTRY")
        while not country:
            country = input(
                "Select country (enter two letters): \n" + "\n".join(
                    [key + " " + value for (key, value) in COUNTRIES.items()]
                ) + "\n"
            )
            if country not in COUNTRIES:
                country = None
        self.country: str = country

        min_date = config_data.get("MIN_DATE")
        try:
            min_date = datetime.strptime(min_date, DATE_FORMAT)
        except ValueError | TypeError:
            min_date = None
        while not min_date:
            try:
                min_date = datetime.strptime(
                    input(
                        "Enter minimal appointment date in format day.month.year "
                        "(example 10.01.2002) or leave blank"
                    ),
                    DATE_FORMAT
                )
            except ValueError:
                pass
        self.min_date: datetime = min_date

        delay_seconds = config_data.get("DELAY_SECONDS")
        try:
            delay_seconds = int(delay_seconds)
        except ValueError | TypeError:
            delay_seconds = None
        while not delay_seconds:
            try:
                delay_seconds = int(input("Delay seconds: "))
            except ValueError:
                pass
        self.delay_seconds: int = delay_seconds

        debug = config_data.get("DEBUG")
        if debug is None:
            debug = input("Do you want to see all logs (Y/N)?: ").upper() == "Y"
        else:
            debug = debug == TRUE
        self.debug = debug

        use_proxy = config_data.get("USE_PROXY")
        if use_proxy is None:
            use_proxy = input("Do you want to use proxy (Y/N)?: ").upper() == "Y"
        else:
            use_proxy = use_proxy == TRUE
        self.use_proxy = use_proxy

        self.facility_id: Optional[str] = config_data.get("FACILITY_ID")

        self.__save()

        if self.use_proxy:
            while not os.path.exists(proxy_path):
                print(
                    f"Create file '{proxy_path}' with proxies list. File's format is:\n"
                    f"socks5://user:password@192.168.1.11:1234\n"
                    f"socks5://user2:password2@192.168.1.12:1235"
                )
                time.sleep(5)

            with open(proxy_path, "r") as f:
                self.proxies = f.readlines()
        else:
            self.proxies = []

    def set_facility_id(self, locations: dict[str, str]):
        if len(locations) == 1:
            self.facility_id = next(iter(locations))
        else:
            facility_id = None
            while not facility_id:
                facility_id = input(
                    "Choose city (enter number): \n" +
                    "\n".join([x[0] + "  " + x[1] for x in locations.items()]) + "\n"
                )
                if facility_id not in locations:
                    facility_id = None
            self.facility_id = facility_id

        self.__save()

    def __save(self):
        with open(self.config_path, "w") as f:
            f.write(
                f"EMAIL={self.email}\nPASSWORD={self.password}\nCOUNTRY={self.country}"
                f"\nDEBUG={self.debug}\nFACILITY_ID={self.facility_id}\nDELAY_SECONDS={self.delay_seconds}"
                f"\nMIN_DATE={self.min_date.strftime(DATE_FORMAT)}\nUSE_PROXY={self.use_proxy}"
            )


class Client:
    def __init__(self, timeout: int, proxy: Optional[str] = None):
        self.timeout = timeout
        self.proxy = proxy

    def post(self, url: str, data: Optional[Any] = None, json: Optional[Any] = None, **kwargs) -> Response:
        if self.proxy:
            return requests.post(
                url=url,
                data=data,
                json=json,
                proxies={"https": self.proxy},
                verify=False,
                timeout=self.timeout,
                **kwargs
            )

        return requests.post(url=url, data=data, json=json, **kwargs)

    def get(self, url: str, params: Optional[Any] = None, **kwargs) -> Response:
        if self.proxy:
            return requests.get(
                url=url,
                params=params,
                proxies={"https": self.proxy},
                verify=False,
                timeout=self.timeout,
                **kwargs
            )

        return requests.get(url=url, params=params, **kwargs)


class Bot:
    def __init__(
            self,
            config: Config,
            logger: Logger,
            client: Client,
            max_error_delay: int,
            sub_bot: bool = False
    ):
        self.logger = logger
        self.client = client
        self.config = config
        self.max_error_delay = max_error_delay
        self.url = f"https://{HOST}/en-{config.country}/niv"

        self.headers: Optional[dict] = None
        self.appointment_datetime: Optional[datetime] = None
        self.schedule_id: Optional[str] = None

        self.last_ping_time = datetime.now()
        if self.config.use_proxy and not sub_bot:
            self.current_sub_bot_index = 0
            self.sub_bots = []
            for proxy in self.config.proxies:
                self.sub_bots.append(Bot(
                    config,
                    logger,
                    Client(self.client.timeout, proxy),
                    max_error_delay,
                    True
                ))

    @staticmethod
    def get_csrf(response: Response) -> str:
        return BeautifulSoup(response.text, HTML_PARSER).find("meta", {"name": "csrf-token"})["content"]

    def with_retry(self, request: Callable[[], Response]) -> Response:
        if not self.headers or not self.schedule_id:
            self.init()

        response = request()
        if response.status_code == UNAUTHORIZED_STATUS:
            self.init()
            response = request()
        return response

    def init(self):
        self.login()
        self.init_current_data()
        self.init_csrf_and_cookie()
        self.logger(
            "Current appointment date and time: "
            f"{self.appointment_datetime.strftime(DATE_TIME_FORMAT)}"
        )

    def login(self):
        self.logger("Get sign in")
        response = self.client.get(
            f"{self.url}/users/sign_in",
            headers={
                COOKIE_HEADER: "",
                REFERER: f"{self.url}/users/sign_in",
                **DOCUMENT_HEADERS
            }
        )
        response.raise_for_status()

        cookies = response.headers.get(SET_COOKIE)

        self.logger("Post sing in")
        response = self.client.post(
            f"{self.url}/users/sign_in",
            headers={
                **DEFAULT_HEADERS,
                X_CSRF_TOKEN_HEADER: Bot.get_csrf(response),
                COOKIE_HEADER: cookies,
                ACCEPT: "*/*;q=0.5, text/javascript, application/javascript, application/ecmascript, "
                        "application/x-ecmascript",
                REFERER: f"{self.url}/users/sign_in",
                CONTENT_TYPE: "application/x-www-form-urlencoded; charset=UTF-8"
            },
            data=urlencode({
                "user[email]": self.config.email,
                "user[password]": self.config.password,
                "policy_confirmed": "1",
                "commit": "Sign In"
            })
        )
        response.raise_for_status()

        self.headers = {COOKIE_HEADER: response.headers.get(SET_COOKIE)}

    def init_current_data(self):
        self.logger("Get current appointment")
        response = self.client.get(
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
        self.headers = {
            COOKIE_HEADER: response.headers.get(SET_COOKIE),
            X_CSRF_TOKEN_HEADER: Bot.get_csrf(response)
        }

    def get_available_facility_id(self) -> dict[str, str]:
        self.logger("Get facility id list")
        locations = (BeautifulSoup(self.load_change_appointment_page().text, HTML_PARSER)
                     .find("select", {"id": "appointments_consulate_appointment_facility_id"})
                     .findAll("option"))
        facility_id_to_location = dict[str, str]()
        for location in locations:
            if location["value"]:
                facility_id_to_location[location["value"]] = location.text
        return facility_id_to_location

    def load_change_appointment_page(self) -> Response:
        self.logger("Get new appointment")
        response = self.client.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment",
            headers={
                **self.headers,
                **DOCUMENT_HEADERS,
                **SEC_FETCH_USER_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/continue_actions"
            }
        )
        response.raise_for_status()
        return response

    def get_available_dates(self) -> list[str]:
        def request() -> Response:
            self.logger("Get available date")
            return self.client.get(
                f"{self.url}/schedule/{self.schedule_id}/appointment/days/"
                f"{self.config.facility_id}.json?appointments[expedite]=false",
                headers={
                    **self.headers,
                    **JSON_HEADERS,
                    REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
                }
            )

        response = self.with_retry(request)
        response.raise_for_status()
        return [x["date"] for x in response.json()]

    def get_available_times(self, available_date) -> list[str]:
        def request() -> Response:
            self.logger("Get available time")
            return self.client.get(
                f"{self.url}/schedule/{self.schedule_id}/appointment/times/{self.config.facility_id}.json?"
                f"date={available_date}&appointments[expedite]=false",
                headers={
                    **self.headers,
                    **JSON_HEADERS,
                    REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
                }
            )

        response = self.with_retry(request)
        response.raise_for_status()
        data = response.json()
        return data["available_times"] or data["business_times"]

    def book(self, available_date: str, available_time: str):
        def request() -> Response:
            self.logger("Book")
            return self.client.post(
                f"{self.url}/schedule/{self.schedule_id}/appointment",
                headers={
                    **self.headers,
                    **DOCUMENT_HEADERS,
                    **SEC_FETCH_USER_HEADERS,
                    CONTENT_TYPE: "application/x-www-form-urlencoded",
                    "Origin": f"https://{HOST}",
                    REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
                },
                data=urlencode({
                    "authenticity_token": self.headers[X_CSRF_TOKEN_HEADER],
                    "confirmed_limit_message": "1",
                    "use_consulate_appointment_capacity": "true",
                    "appointments[consulate_appointment][facility_id]": self.config.facility_id,
                    "appointments[consulate_appointment][date]": available_date,
                    "appointments[consulate_appointment][time]": available_time
                })
            )

        self.with_retry(request)

    def iterate(self):
        use_main_bot = False

        if self.config.use_proxy and (datetime.now() - self.last_ping_time).seconds < PING_DELAY:
            first_sub_bot_index = self.current_sub_bot_index
            available_dates = None
            while available_dates is None:
                try:
                    sub_bot = self.sub_bots[self.current_sub_bot_index]
                    self.logger(f"Use bot with proxy: {sub_bot.client.proxy}")
                    available_dates = sub_bot.get_available_dates()
                except KeyboardInterrupt:
                    exit()
                except Exception as err:
                    self.logger(err)

                self.current_sub_bot_index += 1
                if self.current_sub_bot_index >= len(self.sub_bots):
                    self.current_sub_bot_index = 0

                if first_sub_bot_index == self.current_sub_bot_index:
                    break

            if available_dates is None:
                self.logger("Use main bot")
                use_main_bot = True
                available_dates = self.get_available_dates()
                self.last_ping_time = datetime.now()
        else:
            available_dates = self.get_available_dates()
            self.last_ping_time = datetime.now()

        if not available_dates:
            self.logger("No available dates")
            if use_main_bot:
                raise UseMainBotException()
            return

        if self.appointment_datetime:
            appointment_year = self.appointment_datetime.year
            appointment_month = self.appointment_datetime.month
            appointment_day = self.appointment_datetime.day
        else:
            appointment_year = None
            appointment_month = None
            appointment_day = None

        min_year = self.appointment_datetime.year
        min_month = self.appointment_datetime.month
        min_day = self.appointment_datetime.day

        booked = False

        for available_date in available_dates:
            self.logger(f"Next nearest date: {available_date}")

            year = int(available_date[0:4])
            month = int(available_date[5:7])
            day = int(available_date[8:10])

            if year <= min_year and month <= min_month and day < min_day:
                continue

            if self.appointment_datetime:
                if year > appointment_year or month > appointment_month or day >= appointment_day:
                    break

            available_times = self.get_available_times(available_date)
            if not available_times:
                self.logger("No available times")
                continue

            for available_time in available_times:
                self.logger(f"Next nearest time: {available_time}")

                self.logger(
                    "=====================\n"
                    "#                   #\n"
                    "#                   #\n"
                    "#    Try to book    #\n"
                    "#                   #\n"
                    "#                   #\n"
                    f"# {available_time}  {available_date} #\n"
                    "#                   #\n"
                    "#                   #\n"
                    "=====================",
                    True
                )

                self.book(available_date, available_time)

                appointment_datetime = self.appointment_datetime
                self.init_current_data()

                if appointment_datetime != self.appointment_datetime:
                    self.logger(
                        "=====================\n"
                        "#                   #\n"
                        "#                   #\n"
                        "#     Booked at     #\n"
                        "#                   #\n"
                        "#                   #\n"
                        f"# {self.appointment_datetime.strftime(DATE_TIME_FORMAT)} #\n"
                        "#                   #\n"
                        "#                   #\n"
                        "#  Close window to  #\n"
                        "#    end awaiting   #\n"
                        "=====================",
                        True
                    )
                    booked = True
                    break
            if booked:
                break

        if use_main_bot:
            raise UseMainBotException()

    def process(self):
        self.init()

        if not self.config.facility_id:
            self.config.set_facility_id(self.get_available_facility_id())

        errors_count = 0
        while True:
            if self.appointment_datetime and self.appointment_datetime < self.config.min_date:
                self.logger("Current appointment date and time lower than specified minimal date")
                break

            try:
                self.iterate()
                errors_count = max(0, errors_count - 1)
            except KeyboardInterrupt:
                exit()
            except UseMainBotException:
                time.sleep(PING_DELAY)
            except Exception as err:
                self.logger(err)
                errors_count += 1

            time.sleep(self.config.delay_seconds + min(
                self.max_error_delay,
                errors_count * self.config.delay_seconds
            ))


def main():
    config = Config(CONFIG_FILE, PROXY_FILE)
    logger = Logger(config.debug)
    client = Client(TIMEOUT)
    Bot(config, logger, client, MAX_ERROR_DELAY).process()


if __name__ == "__main__":
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        main()
    except KeyboardInterrupt:
        pass
