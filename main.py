import os.path
import os.path
import re
import time
from datetime import datetime
from typing import Optional, Callable, TypeVar
from urllib.parse import urlencode

import requests
import urllib3
from bs4 import BeautifulSoup
from requests import Response, HTTPError

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
Y = "Y"
T = TypeVar('T')

CONFIG_FILE = "config"
TIMEOUT = 4
MAX_ERROR_DELAY = 4 * 60 * 60


class NoScheduleIdException(Exception):
    def __init__(self):
        super().__init__("No schedule id")


class Logger:
    def __init__(self, debug: bool = True):
        self.debug = debug

    def __call__(self, message: str | Exception, force: bool = False):
        if self.debug or force:
            print(f"[{datetime.now().strftime(DATE_TIME_FORMAT)}] {message}")


class Config:
    def __init__(self, config_path: str):
        self.config_path = config_path

        config_data = dict()
        if not os.path.exists(self.config_path):
            open(self.config_path, 'w').close()
        with open(self.config_path, "r") as f:
            for line in f.readlines():
                param = line.strip().split("=", maxsplit=1)
                if len(param) == 2:
                    value = param[1].strip()
                    if value and value != "None":
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
            if min_date:
                min_date = datetime.strptime(min_date, DATE_FORMAT)
        except ValueError | TypeError:
            min_date = None
        while not min_date:
            try:
                min_date = input(
                    "Enter minimal appointment date in format day.month.year "
                    "(example 10.01.2002) or leave blank"
                )
                if min_date:
                    min_date = datetime.strptime(min_date, DATE_FORMAT)
                else:
                    min_date = datetime.now()
            except ValueError | TypeError:
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
            debug = input("Do you want to see all logs (Y/N)?: ").upper() == Y
        else:
            debug = debug == TRUE
        self.debug = debug

        need_asc = config_data.get("NEED_ASC")
        if need_asc is None:
            need_asc = input("Do you need ASC registration (Y/N)?: ").upper() == Y
        else:
            need_asc = need_asc == TRUE
        self.need_asc = need_asc

        self.facility_id: Optional[str] = config_data.get("FACILITY_ID")
        self.asc_facility_id: Optional[str] = config_data.get("ASC_FACILITY_ID")

        self.__save()

    def set_facility_id(self, locations: dict[str, str]):
        self.facility_id = self.__choose_location(locations, "consul")
        self.__save()

    def set_asc_facility_id(self, locations: dict[str, str]):
        self.asc_facility_id = self.__choose_location(locations, "asc")
        self.__save()

    @staticmethod
    def __choose_location(locations: dict[str, str], location_name: str) -> str:
        if len(locations) == 1:
            return next(iter(locations))

        facility_id = None
        while not facility_id:
            facility_id = input(
                f"Choose {location_name} location (enter number): \n" +
                "\n".join([x[0] + "  " + x[1] for x in locations.items()]) + "\n"
            )
            if facility_id not in locations:
                facility_id = None
        return facility_id

    def __save(self):
        with open(self.config_path, "w") as f:
            f.write(
                f"EMAIL={self.email}"
                f"\nPASSWORD={self.password}"
                f"\nCOUNTRY={self.country}"
                f"\nDEBUG={self.debug}"
                f"\nFACILITY_ID={self.facility_id}"
                f"\nDELAY_SECONDS={self.delay_seconds}"
                f"\nMIN_DATE={self.min_date.strftime(DATE_FORMAT)}"
                f"\nNEED_ASC={self.need_asc}"
                f"\nASC_FACILITY_ID={self.asc_facility_id}"
            )


class Bot:
    def __init__(self, config: Config, logger: Logger, max_error_delay: int):
        self.logger = logger
        self.config = config
        self.max_error_delay = max_error_delay
        self.url = f"https://{HOST}/en-{config.country}/niv"

        self.appointment_datetime: Optional[datetime] = None
        self.schedule_id: Optional[str] = None
        self.csrf: Optional[str] = None
        self.cookie: Optional[str] = None

    @staticmethod
    def get_csrf(response: Response) -> str:
        return BeautifulSoup(response.text, HTML_PARSER).find("meta", {"name": "csrf-token"})["content"]

    def with_retry(self, request: Callable[[], T]) -> T:
        if not self.cookie or not self.schedule_id or not self.csrf:
            self.logger(f"Not found cookie ({self.cookie}), schedule_id ({self.schedule_id}) or csrf ({self.csrf})")
            self.init()

        try:
            response = request()
        except HTTPError as err:
            if err.response.status_code == UNAUTHORIZED_STATUS:
                self.logger("Get 401")
                self.init()
                response = request()
            else:
                raise err

        if isinstance(response, Response) and response.status_code == UNAUTHORIZED_STATUS:
            self.logger("Get 401")
            self.init()
            response = request()
        return response

    def headers(self) -> dict[str, str]:
        headers = dict()

        if self.cookie:
            headers[COOKIE_HEADER] = self.cookie

        if self.csrf:
            headers[X_CSRF_TOKEN_HEADER] = self.csrf

        return headers

    def init(self):
        self.login()
        self.init_current_data()
        self.init_csrf_and_cookie()

        if not self.config.facility_id:
            self.logger("Not found facility_id")
            self.config.set_facility_id(self.get_available_facility_id())

        if self.config.need_asc and not self.config.asc_facility_id:
            self.logger("Not found asc_facility_id")
            self.config.set_asc_facility_id(self.get_available_asc_facility_id())

        self.logger(
            "Current appointment date and time: "
            f"{self.appointment_datetime.strftime(DATE_TIME_FORMAT)}"
        )

    def login(self):
        self.logger("Get sign in")
        response = requests.get(
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
        response = requests.post(
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
        self.cookie = response.headers.get(SET_COOKIE)

    def init_current_data(self):
        self.logger("Get current appointment")
        response = requests.get(
            self.url,
            headers={
                **self.headers(),
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
        self.cookie = response.headers.get(SET_COOKIE)
        self.csrf = Bot.get_csrf(response)

    def get_available_locations(self, element_id: str) -> dict[str, str]:
        self.logger("Get location list")
        locations = (BeautifulSoup(self.load_change_appointment_page().text, HTML_PARSER)
                     .find("select", {"id": element_id})
                     .findAll("option"))
        facility_id_to_location = dict[str, str]()
        for location in locations:
            if location["value"]:
                facility_id_to_location[location["value"]] = location.text
        return facility_id_to_location

    def get_available_facility_id(self) -> dict[str, str]:
        self.logger("Get facility id list")
        return self.get_available_locations("appointments_consulate_appointment_facility_id")

    def get_available_asc_facility_id(self) -> dict[str, str]:
        self.logger("Get asc facility id list")
        return self.get_available_locations("appointments_asc_appointment_facility_id")

    def load_change_appointment_page(self) -> Response:
        self.logger("Get new appointment")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment",
            headers={
                **self.headers(),
                **DOCUMENT_HEADERS,
                **SEC_FETCH_USER_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/continue_actions"
            }
        )
        response.raise_for_status()
        return response

    def get_available_dates(self) -> list[str]:
        self.logger("Get available date")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/days/"
            f"{self.config.facility_id}.json?appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        dates = [x["date"] for x in response.json()]
        dates.sort()
        return dates

    def get_available_times(self, available_date: str) -> list[str]:
        self.logger("Get available time")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/times/{self.config.facility_id}.json?"
            f"date={available_date}&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        data = response.json()
        times = data["available_times"] or data["business_times"]
        times.sort()
        return times

    def get_asc_available_dates(self, available_date: str, available_time: str) -> list[str]:
        self.logger("Get available dates ASC")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/days/"
            f"{self.config.asc_facility_id}.json?&consulate_id={self.config.facility_id}"
            f"&consulate_date={available_date}&consulate_time={available_time}&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        dates = [x["date"] for x in response.json()]
        dates.sort()
        return dates

    def get_asc_available_times(self, available_date: str, available_time: str, asc_available_date: str) -> list[str]:
        self.logger("Get available times ASC")
        response = requests.get(
            f"{self.url}/schedule/{self.schedule_id}/appointment/times/{self.config.asc_facility_id}.json?"
            f"date={asc_available_date}&consulate_id={self.schedule_id}&consulate_date={available_date}"
            f"&consulate_time={available_time}&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        data = response.json()
        times = data["available_times"] or data["business_times"]
        times.sort()
        return times

    def book(
            self,
            available_date: str,
            available_time: str,
            asc_available_date: Optional[str],
            asc_available_time: Optional[str]
    ):
        def request() -> Response:
            self.logger("Book")

            body = {
                "authenticity_token": self.csrf,
                "confirmed_limit_message": "1",
                "use_consulate_appointment_capacity": "true",
                "appointments[consulate_appointment][facility_id]": self.config.facility_id,
                "appointments[consulate_appointment][date]": available_date,
                "appointments[consulate_appointment][time]": available_time
            }

            if asc_available_date and available_time:
                self.logger("Add ASC date and time to request")
                body = {
                    **body,
                    "appointments[asc_appointment][facility_id]": self.config.asc_facility_id,
                    "appointments[asc_appointment][date]": asc_available_date,
                    "appointments[asc_appointment][time]": asc_available_time
                }

            self.logger(f"Request {body}")

            return requests.post(
                f"{self.url}/schedule/{self.schedule_id}/appointment",
                headers={
                    **self.headers(),
                    **DOCUMENT_HEADERS,
                    **SEC_FETCH_USER_HEADERS,
                    CONTENT_TYPE: "application/x-www-form-urlencoded",
                    "Origin": f"https://{HOST}",
                    REFERER: f"{self.url}/schedule/{self.schedule_id}/appointment"
                },
                data=urlencode(body)
            )

        self.with_retry(request)

    def iterate(self):
        available_dates = self.get_available_dates()

        if not available_dates:
            self.logger("No available dates")
            return

        self.logger(f"All available dates: {available_dates}")

        for available_date in available_dates:
            self.logger(f"Next nearest date: {available_date}")

            year = int(available_date[0:4])
            month = int(available_date[5:7])
            day = int(available_date[8:10])

            if (year <= self.config.min_date.year
                    and month <= self.config.min_date.month
                    and day < self.config.min_date.day):
                self.logger(
                    f"Nearest date is lower than your minimal date {self.config.min_date.strftime(DATE_FORMAT)}"
                )
                continue

            if self.appointment_datetime:
                if (year > self.appointment_datetime.year
                        or month > self.appointment_datetime.month
                        or day >= self.appointment_datetime.day):
                    self.logger(
                        "Nearest date is greater than your current date "
                        f"{self.appointment_datetime.strftime(DATE_FORMAT)}"
                    )
                    break

            available_times = self.get_available_times(available_date)
            if not available_times:
                self.logger("No available times")
                continue

            self.logger(f"All available for date {available_date} times: {available_times}")

            for available_time in available_times:
                self.logger(f"Next nearest time: {available_time}")

                asc_available_date = None
                asc_available_time = None

                if self.config.need_asc:
                    asc_available_dates = self.get_asc_available_dates(
                        available_date,
                        available_time
                    )

                    if not asc_available_dates:
                        self.logger("No available ASC dates")
                        return

                    asc_available_date = asc_available_dates[0]

                    asc_available_times = self.get_asc_available_times(
                        available_date,
                        available_time,
                        asc_available_date
                    )

                    if not asc_available_times:
                        self.logger("No available ASC times")
                        continue

                    asc_available_time = asc_available_times[0]

                log = (
                    "=====================\n"
                    "#                   #\n"
                    "#                   #\n"
                    "#    Try to book    #\n"
                    "#                   #\n"
                    "#                   #\n"
                    f"# {available_time}  {available_date} #\n"
                )

                if asc_available_date and asc_available_time:
                    log += (
                        "#                   #\n"
                        "#                   #\n"
                        "#     With  ASC     #\n"
                        f"# {asc_available_time}  {asc_available_date} #\n"
                    )

                log += (
                    "#                   #\n"
                    "#                   #\n"
                    "====================="
                )

                self.logger(log, True)

                self.book(
                    available_date,
                    available_time,
                    asc_available_date,
                    asc_available_time
                )

                appointment_datetime = self.appointment_datetime
                self.init_current_data()

                if appointment_datetime != self.appointment_datetime:
                    log = (
                        "=====================\n"
                        "#                   #\n"
                        "#                   #\n"
                        "#     Booked at     #\n"
                        "#                   #\n"
                        "#                   #\n"
                        f"# {self.appointment_datetime.strftime(DATE_TIME_FORMAT)} #\n"
                    )

                    if asc_available_date and asc_available_time:
                        log += (
                            "#                   #\n"
                            "#                   #\n"
                            "#     With  ASC     #\n"
                            f"# {asc_available_time}  {asc_available_date} #\n"
                        )

                    log += (
                        "#                   #\n"
                        "#                   #\n"
                        "#  Close window to  #\n"
                        "#    end awaiting   #\n"
                        "====================="
                    )

                    self.logger(log, True)
                    return

    def process(self):
        errors_count = 0
        while True:
            try:
                if self.appointment_datetime and self.appointment_datetime <= self.config.min_date:
                    self.logger("Current appointment date and time lower than specified minimal date")
                    break

                self.with_retry(self.iterate)
                errors_count = max(0, errors_count - 1)
            except KeyboardInterrupt:
                return
            except Exception as err:
                self.logger(err)
                errors_count += 1

            time.sleep(self.config.delay_seconds + min(
                self.max_error_delay,
                errors_count * self.config.delay_seconds
            ))


def main():
    config = Config(CONFIG_FILE)
    logger = Logger(config.debug)
    Bot(config, logger, MAX_ERROR_DELAY).process()


if __name__ == "__main__":
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        main()
    except KeyboardInterrupt:
        pass
