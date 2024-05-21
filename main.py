import json
import logging
import os.path
import random
import re
import time
from datetime import datetime, date, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
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
HTML_PARSER = "html.parser"
NONE = "None"

CONFIG_FILE = "config"
ASC_FILE = "asc"
LOG_FILE = "log.txt"
LOG_FORMAT = "%(asctime)s  %(message)s"


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class NoScheduleIdException(Exception):
    def __init__(self):
        super().__init__("No schedule id")


class AppointmentDateLowerMinDate(Exception):
    def __init__(self):
        super().__init__("Current appointment date and time lower than specified minimal date")


class Logger:
    def __init__(self, log_file: str, log_format: str):
        log_formatter = logging.Formatter(log_format)
        root_logger = logging.getLogger()

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        root_logger.addHandler(console_handler)

        root_logger.setLevel("DEBUG")

        self.root_logger = root_logger

    def __call__(self, message: str | Exception):
        self.root_logger.debug(message, exc_info=isinstance(message, Exception))


class Appointment:
    def __init__(self, schedule_id: str, description: str, appointment_datetime: Optional[datetime]):
        self.schedule_id = schedule_id
        self.description = description
        self.appointment_datetime = appointment_datetime


class Config:
    def __init__(self, config_file: str):
        self.config_file = config_file

        config_data = dict()
        if not os.path.exists(self.config_file):
            open(self.config_file, 'w').close()
        with open(self.config_file, "r") as f:
            for line in f.readlines():
                param = line.strip().split("=", maxsplit=1)
                if len(param) == 2:
                    key = param[0].strip()
                    value = param[1].strip()
                    if value and value != NONE:
                        config_data[key] = param[1].strip()
                    else:
                        config_data[key] = None

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
                    "(example 10.01.2002) or leave blank: "
                )
                if min_date:
                    min_date = datetime.strptime(min_date, DATE_FORMAT)
                else:
                    min_date = datetime.now()
            except ValueError | TypeError:
                pass
        self.min_date: date = min_date.date()

        init_max_date = "MAX_DATE" not in config_data
        max_date = config_data.get("MAX_DATE")
        try:
            if max_date:
                max_date = datetime.strptime(max_date, DATE_FORMAT)
        except ValueError | TypeError:
            max_date = None
        if init_max_date:
            while True:
                try:
                    max_date = input(
                        "Enter maximal appointment date in format day.month.year "
                        "(example 10.01.2002) or leave blank (but make note, "
                        "it may lead to the exhaustion of the transfer limit): "
                    )
                    if max_date:
                        max_date = datetime.strptime(max_date, DATE_FORMAT)
                    else:
                        max_date = None
                    break
                except ValueError | TypeError:
                    pass
        self.max_date: Optional[date] = max_date.date() if max_date else None

        need_asc = config_data.get("NEED_ASC")
        if need_asc is None:
            need_asc = input(
                "Do you need ASC registration (Y/N. Enter N, if you don't know, what is it)?: "
            ).upper() == "Y"
        else:
            need_asc = need_asc == "True"
        self.need_asc = need_asc

        self.schedule_id: Optional[str] = config_data.get("SCHEDULE_ID")

        if self.schedule_id:
            self.facility_id: Optional[str] = config_data.get("FACILITY_ID")
            self.asc_facility_id: Optional[str] = config_data.get("ASC_FACILITY_ID")
        else:
            self.facility_id = None
            self.asc_facility_id = None

        self.__save()

    def set_facility_id(self, locations: dict[str, str]):
        self.facility_id = self.__choose_location(locations, "consul")
        self.__save()

    def set_asc_facility_id(self, locations: dict[str, str]):
        self.asc_facility_id = self.__choose_location(locations, "asc")
        self.__save()

    def set_schedule_id(self, schedule_ids: dict[str, Appointment]):
        self.schedule_id = Config.__choose(
            schedule_ids,
            f"Choose schedule id (enter number): \n" +
            "\n".join([x[0] + "  " + x[1].description for x in schedule_ids.items()]) + "\n"
        )
        self.__save()

    @staticmethod
    def __choose_location(locations: dict[str, str], location_name: str) -> str:
        return Config.__choose(
            locations,
            f"Choose {location_name} location (enter number): \n" +
            "\n".join([x[0] + "  " + x[1] for x in locations.items()]) + "\n"
        )

    @staticmethod
    def __choose(values: dict, message: str) -> str:
        if len(values) == 1:
            return next(iter(values))

        value = None
        while not value:
            value = input(message)
            if value not in values:
                value = None
        return value

    def __save(self):
        with open(self.config_file, "w") as f:
            f.write(
                f"EMAIL={self.email}"
                f"\nPASSWORD={self.password}"
                f"\nCOUNTRY={self.country}"
                f"\nFACILITY_ID={self.facility_id}"
                f"\nMIN_DATE={self.min_date.strftime(DATE_FORMAT)}"
                f"\nMAX_DATE={self.max_date.strftime(DATE_FORMAT) if self.max_date else NONE}"
                f"\nNEED_ASC={self.need_asc}"
                f"\nASC_FACILITY_ID={self.asc_facility_id}"
                f"\nSCHEDULE_ID={self.schedule_id}"
            )


class Bot:
    def __init__(self, config: Config, logger: Logger, asc_file: str):
        self.logger = logger
        self.config = config
        self.asc_file = asc_file
        self.url = f"https://{HOST}/en-{config.country}/niv"

        self.appointment_datetime: Optional[datetime] = None
        self.csrf: Optional[str] = None
        self.cookie: Optional[str] = None
        self.session = requests.session()
        self.asc_dates = dict()

    @staticmethod
    def get_csrf(response: Response) -> str:
        return BeautifulSoup(response.text, HTML_PARSER).find("meta", {"name": "csrf-token"})["content"]

    def headers(self) -> dict[str, str]:
        headers = dict()

        if self.cookie:
            headers[COOKIE_HEADER] = self.cookie

        if self.csrf:
            headers[X_CSRF_TOKEN_HEADER] = self.csrf

        return headers

    def init(self):
        # noinspection PyBroadException
        try:
            self.session.close()
        except Exception:
            pass
        self.session = requests.Session()

        self.login()
        self.init_current_data()
        self.init_csrf_and_cookie()

        if not self.config.facility_id:
            self.logger("Not found facility_id")
            self.config.set_facility_id(self.get_available_facility_id())

        if self.config.need_asc and not self.config.asc_facility_id:
            self.logger("Not found asc_facility_id")
            self.config.set_asc_facility_id(self.get_available_asc_facility_id())

        self.init_asc_dates()

        self.logger(
            "Current appointment date and time: "
            f"{self.appointment_datetime.strftime(DATE_TIME_FORMAT) if self.appointment_datetime else 'No date'}"
        )

    def login(self):
        self.logger("Get sign in")
        response = self.session.get(
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
        response = self.session.post(
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
        response = self.session.get(
            self.url,
            headers={
                **self.headers(),
                **DOCUMENT_HEADERS
            }
        )
        response.raise_for_status()

        applications = BeautifulSoup(response.text, HTML_PARSER).findAll("div", {"class": "application"})

        if not applications:
            raise NoScheduleIdException()

        schedule_ids = dict()

        for application in applications:
            schedule_id = re.search(r"\d+", str(application.find("a")))

            if not schedule_id:
                continue

            schedule_id = schedule_id.group(0)
            description = ' '.join([x.get_text() for x in application.findAll("td")][0:4])
            appointment_datetime = application.find("p", {"class": "consular-appt"})
            if appointment_datetime:
                appointment_datetime = re.search(r"\d{1,2} \w+?, \d{4}, \d{1,2}:\d{1,2}",
                                                 appointment_datetime.get_text())

                if appointment_datetime:
                    appointment_datetime = datetime.strptime(appointment_datetime.group(0), "%d %B, %Y, %H:%M")
                else:
                    appointment_datetime = None

            schedule_ids[schedule_id] = Appointment(schedule_id, description, appointment_datetime)

        if not self.config.schedule_id:
            self.config.set_schedule_id(schedule_ids)

        self.appointment_datetime = schedule_ids[self.config.schedule_id].appointment_datetime

        if self.appointment_datetime and self.appointment_datetime.date() <= self.config.min_date:
            raise AppointmentDateLowerMinDate()

    def init_asc_dates(self):
        if not self.config.need_asc or not self.config.asc_facility_id:
            return

        if not os.path.exists(self.asc_file):
            open(self.asc_file, 'w').close()
        with open(self.asc_file) as f:
            # noinspection PyBroadException
            try:
                self.asc_dates = json.load(f)
            except:
                pass

        dates_temp = None

        # noinspection PyBroadException
        try:
            dates_temp = self.get_asc_available_dates()
        except:
            pass

        if dates_temp:
            dates = []
            for x in dates_temp:
                date_temp = parse_date(x)
                if self.config.min_date <= date_temp <= self.config.max_date:
                    dates.append(x)

            if len(dates) > 0:
                self.asc_dates = dict()
                for x in dates:
                    # noinspection PyBroadException
                    try:
                        self.asc_dates[x] = self.get_asc_available_times(x)
                    except:
                        pass

        with open(self.asc_file, 'w') as f:
            json.dump(self.asc_dates, f)

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
        response = self.session.get(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment",
            headers={
                **self.headers(),
                **DOCUMENT_HEADERS,
                **SEC_FETCH_USER_HEADERS,
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/continue_actions"
            }
        )
        response.raise_for_status()
        return response

    def get_available_dates(self) -> list[str]:
        self.logger("Get available date")
        response = self.session.get(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment/days/"
            f"{self.config.facility_id}.json?appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/appointment"
            }
        )
        response.raise_for_status()

        data = response.json()
        self.logger(f"Response: {data}")
        dates = [x["date"] for x in data]
        dates.sort()
        return dates

    def get_available_times(self, available_date: str) -> list[str]:
        self.logger("Get available time")
        response = self.session.get(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment/times/{self.config.facility_id}.json?"
            f"date={available_date}&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        data = response.json()
        self.logger(f"Response: {data}")
        times = data["available_times"] or data["business_times"]
        times.sort()
        return times

    def get_asc_available_dates(
            self,
            available_date: Optional[str] = None,
            available_time: Optional[str] = None
    ) -> list[str]:
        self.logger("Get available dates ASC")
        response = self.session.get(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment/days/"
            f"{self.config.asc_facility_id}.json?&consulate_id={self.config.facility_id}"
            f"&consulate_date={available_date if available_date else ''}"
            f"&consulate_time={available_time if available_time else ''}"
            f"&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        data = response.json()
        self.logger(f"Response: {data}")
        dates = [x["date"] for x in data]
        dates.sort()
        return dates

    def get_asc_available_times(
            self,
            asc_available_date: str,
            available_date: Optional[str] = None,
            available_time: Optional[str] = None
    ) -> list[str]:
        self.logger("Get available times ASC")
        response = self.session.get(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment/times/{self.config.asc_facility_id}.json?"
            f"date={asc_available_date}&consulate_id={self.config.schedule_id}"
            f"&consulate_date={available_date if available_date else ''}"
            f"&consulate_time={available_time if available_time else ''}"
            f"&appointments[expedite]=false",
            headers={
                **self.headers(),
                **JSON_HEADERS,
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/appointment"
            }
        )
        response.raise_for_status()
        data = response.json()
        self.logger(f"Response: {data}")
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

        return self.session.post(
            f"{self.url}/schedule/{self.config.schedule_id}/appointment",
            headers={
                **self.headers(),
                **DOCUMENT_HEADERS,
                **SEC_FETCH_USER_HEADERS,
                CONTENT_TYPE: "application/x-www-form-urlencoded",
                "Origin": f"https://{HOST}",
                REFERER: f"{self.url}/schedule/{self.config.schedule_id}/appointment"
            },
            data=urlencode(body)
        )

    def process(self):
        self.init()
        while True:
            time.sleep(1.5)
            try:
                now = datetime.now()
                mod = now.minute % 5

                if mod != 0 or now.second < 10:
                    if now.second % 10 == 0:
                        self.logger("Wait")
                    continue

                try:
                    available_dates = self.get_available_dates()
                except HTTPError as err:
                    if err.response.status_code != 401:
                        raise err

                    self.logger("Get 401")
                    self.init()
                    available_dates = self.get_available_dates()

                if not available_dates:
                    self.logger("No available dates")
                    continue

                self.logger(f"All available dates: {available_dates}")

                reinit_asc = False
                for available_date_str in available_dates:
                    self.logger(f"Next nearest date: {available_date_str}")

                    available_date = parse_date(available_date_str)

                    if available_date <= self.config.min_date:
                        self.logger(
                            "Nearest date is lower than your minimal date "
                            f"{self.config.min_date.strftime(DATE_FORMAT)}"
                        )
                        continue

                    if self.appointment_datetime and available_date >= self.appointment_datetime.date():
                        self.logger(
                            "Nearest date is greater than your current date "
                            f"{self.appointment_datetime.strftime(DATE_FORMAT)}"
                        )
                        break

                    if self.config.max_date and available_date > self.config.max_date:
                        self.logger(
                            "Nearest date is greater than your maximal date "
                            f"{self.config.max_date.strftime(DATE_FORMAT)}"
                        )
                        break

                    available_times = self.get_available_times(available_date_str)
                    if not available_times:
                        self.logger("No available times")
                        continue

                    self.logger(f"All available times for date {available_date_str}: {available_times}")

                    booked = False
                    for available_time_str in available_times:
                        self.logger(f"Next nearest time: {available_time_str}")

                        asc_available_date_str = None
                        asc_available_time_str = None

                        if self.config.need_asc:
                            asc_available_date_str = None
                            asc_available_time_str = None

                            min_asc_date = available_date - timedelta(days=7)

                            for k, v in self.asc_dates.items():
                                if min_asc_date <= parse_date(k) < available_date and len(v) > 0:
                                    asc_available_date_str = k
                                    asc_available_time_str = random.choice(v)
                                    break

                            if not asc_available_date_str or not asc_available_time_str:
                                asc_available_dates = self.get_asc_available_dates(
                                    available_date_str,
                                    available_time_str
                                )

                                if not asc_available_dates:
                                    self.logger("No available ASC dates")
                                    break

                                asc_available_date_str = asc_available_dates[0]

                                asc_available_times = self.get_asc_available_times(
                                    asc_available_date_str,
                                    available_date_str,
                                    available_time_str
                                )

                                if not asc_available_times:
                                    self.logger("No available ASC times")
                                    continue

                                asc_available_time_str = random.choice(asc_available_times)

                        log = (
                            "=====================\n"
                            "#                   #\n"
                            "#                   #\n"
                            "#    Try to book    #\n"
                            "#                   #\n"
                            "#                   #\n"
                            f"# {available_time_str}  {available_date_str} #\n"
                        )

                        if asc_available_date_str and asc_available_time_str:
                            log += (
                                "#                   #\n"
                                "#                   #\n"
                                "#     With  ASC     #\n"
                                f"# {asc_available_time_str}  {asc_available_date_str} #\n"
                            )

                        log += (
                            "#                   #\n"
                            "#                   #\n"
                            "====================="
                        )

                        self.logger(log)

                        self.book(
                            available_date_str,
                            available_time_str,
                            asc_available_date_str,
                            asc_available_time_str
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

                            if asc_available_date_str and asc_available_time_str:
                                log += (
                                    "#                   #\n"
                                    "#                   #\n"
                                    "#     With  ASC     #\n"
                                    f"# {asc_available_time_str}  {asc_available_date_str} #\n"
                                )

                            log += (
                                "#                   #\n"
                                "#                   #\n"
                                "#  Close window to  #\n"
                                "#    end awaiting   #\n"
                                "====================="
                            )

                            self.logger(log)
                            booked = True
                            break

                    reinit_asc = True

                    if booked:
                        break

                if reinit_asc and self.config.need_asc:
                    self.init_asc_dates()

            except KeyboardInterrupt:
                return
            except AppointmentDateLowerMinDate as err:
                self.logger(err)
                return
            except Exception as err:
                self.logger(err)


def main():
    config = Config(CONFIG_FILE)
    logger = Logger(LOG_FILE, LOG_FORMAT)
    Bot(config, logger, ASC_FILE).process()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
