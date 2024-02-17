import os.path
import re
import time
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlencode
import getpass

import requests
from bs4 import BeautifulSoup

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


class NoScheduleIdException(Exception):
    def __init__(self):
        super().__init__("No schedule id")


class Logger:
    def __init__(self, debug: bool = True):
        self.debug = debug

    def log(self, message: str | Exception, force: bool = False):
        if self.debug or force:
            print(f"[{datetime.now().isoformat()}] {message}")


def login(url: str, email: str, password: str) -> dict:
    response = requests.get(f"{url}/users/sign_in", headers={
        "Cookie": "",
        "Referer": f"{url}/users/sign_in",
        **DOCUMENT_HEADERS
    })
    response.raise_for_status()

    cookies = response.headers.get("set-cookie")

    soup = BeautifulSoup(response.text, "html.parser")
    csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]

    response = requests.post(f"{url}/users/sign_in", headers={
        **DEFAULT_HEADERS,
        X_CSRF_TOKEN_HEADER: csrf_token,
        "Cookie": cookies,
        "Accept": "*/*;q=0.5, text/javascript, application/javascript, application/ecmascript, "
                  "application/x-ecmascript",
        "Referer": f"{url}/users/sign_in",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }, data=urlencode({
        "user[email]": email,
        "user[password]": password,
        "policy_confirmed": "1",
        "commit": "Sign In"
    }))
    response.raise_for_status()

    return {"Cookie": response.headers.get("set-cookie")}


def get_current_appointment_data(url: str, country: str, headers: dict) -> Tuple[datetime | None, str]:
    login_response = requests.get(url, headers={
        **headers,
        **DOCUMENT_HEADERS
    })
    login_response.raise_for_status()

    login_data = login_response.text

    match = re.search(r"\d{2} \w+?, \d{4}, \d{2}:\d{2}", login_data)
    current_date_time = None
    if match:
        current_date_time = datetime.strptime(match.group(0), "%d %B, %Y, %H:%M")

    match = re.search(rf"href=\"/en-{country}/niv/schedule/(\d+)/continue_actions\">Continue</a>", login_data)
    if not match:
        raise NoScheduleIdException()

    schedule_id = match.group(1)

    return current_date_time, schedule_id


def get_new_appointment_data(url: str, schedule_id: str, headers: dict) -> tuple[dict, dict]:
    response = requests.get(
        f"{url}/schedule/{schedule_id}/appointment",
        headers={
            **headers,
            "Sec-Fetch-User": "?1",
            "Referer": f"{url}/schedule/{schedule_id}/continue_actions",
            **DOCUMENT_HEADERS
        }
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]

    locations = (soup
                 .find("select", {"id": "appointments_consulate_appointment_facility_id"})
                 .findAll("option"))
    clear_locations = dict()
    for location in locations:
        if location["value"]:
            clear_locations[location["value"]] = location.text

    return clear_locations, {**headers, X_CSRF_TOKEN_HEADER: csrf_token}


def get_available_date(url: str, schedule_id: str, facility_id: str, headers: dict) -> str | None:
    response = requests.get(
        f"{url}/schedule/{schedule_id}/appointment/days/{facility_id}.json?appointments[expedite]=false",
        headers={
            **headers,
            **JSON_HEADERS,
            "Referer": f"{url}/schedule/{schedule_id}/appointment"
        }
    )
    response.raise_for_status()

    data = response.json()
    return data[0]["date"] if len(data) > 0 else None


def get_available_time(url: str, schedule_id: str, facility_id: str, date: str, headers: dict) -> str:
    response = requests.get(
        f"{url}/schedule/{schedule_id}/appointment/times/{facility_id}.json?date={date}&"
        f"appointments[expedite]=false",
        headers={
            **headers,
            **JSON_HEADERS,
            "Referer": f"{url}/schedule/{schedule_id}/appointment"
        }
    )
    response.raise_for_status()

    data = response.json()

    return data["business_times"][0] or data["available_times"][0]


def book(url: str, schedule_id: str, facility_id: str, book_date: str, book_time: str, headers: dict):
    response = requests.post(
        f"{url}/schedule/{schedule_id}/appointment",
        headers={
            **headers,
            **DOCUMENT_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Sec-Fetch-User": "?1",
            "Origin": f"https://{HOST}",
            "Referer": f"{url}/schedule/{schedule_id}/appointment"
        },
        data=urlencode({
            "authenticity_token": headers[X_CSRF_TOKEN_HEADER],
            "confirmed_limit_message": "1",
            "use_consulate_appointment_capacity": "true",
            "appointments[consulate_appointment][facility_id]": facility_id,
            "appointments[consulate_appointment][date]": book_date,
            "appointments[consulate_appointment][time]": book_time
        })
    )
    response.raise_for_status()


def get_data(logger: Logger, url: str, email: str, password: str, country: str) \
        -> tuple[datetime | None, str, dict, dict]:
    logger.log("Logging in")
    headers = login(url, email, password)

    logger.log("Get appointment data")
    (current_date_time, schedule_id) = get_current_appointment_data(url, country, headers)

    logger.log("Get new appointment data")
    (locations, headers) = get_new_appointment_data(url, schedule_id, headers)

    return current_date_time, schedule_id, headers, locations


def load_config() -> tuple[bool, str, str, str, str | None, Logger]:
    config = dict()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            for line in f.readlines():
                param = line.strip().split("=", maxsplit=1)
                if len(param) == 2:
                    config[param[0].strip()] = param[1].strip()

    email = config.get("EMAIL")
    password = config.get("PASSWORD")
    country = config.get("COUNTRY")
    facility_id = config.get("FACILITY_ID")
    debug = bool(config.get("DEBUG")) if config.get("DEBUG") else None

    try_login = False

    if not email:
        try_login = True
        email = input("Enter email: ")
    if not password:
        try_login = True
        password = getpass.getpass("Enter password: ")
    while not country:
        try_login = True
        country = input(
            "Select country (enter two letters) \n" + "\n".join(
                [key + " " + value for (key, value) in COUNTRIES.items()]))
        if country not in COUNTRIES:
            country = None
    if not debug:
        debug = input("Do you want to see all logs (Y/N)?: ").upper() == "Y"

    return try_login, email, password, country, facility_id, Logger(debug)


def save_config(email: str, password: str, country: str, facility_id: str, debug: bool):
    with open("config", "w") as f:
        f.write(f"EMAIL={email}\nPASSWORD={password}\nCOUNTRY={country}\nDEBUG={debug}\nFACILITY_ID={facility_id}")


def get_facility_id(locations: dict) -> str:
    if len(locations) > 1:
        num = None
        while not num:
            num = input("Choose city (enter number) \n" +
                        "\n".join([x[0] + "  " + x[1] for x in locations.items()])) + "\n"
            if num not in locations:
                num = None
        return num
    else:
        return next(iter(locations))


def main():
    try_login, email, password, country, facility_id, logger = load_config()
    url = f"https://{HOST}/en-{country}/niv"

    headers: Optional[dict] = None
    current_date_time: Optional[datetime] = None
    schedule_id: Optional[str] = None

    if try_login:
        current_date_time, schedule_id, headers, locations = get_data(logger, url, email, password, country)
        if not facility_id:
            facility_id = get_facility_id(locations)
        save_config(email, password, country, facility_id, logger.debug)

    errors_count = 0
    no_dates_available_count = 0

    while True:
        try:
            if not headers:
                current_date_time, schedule_id, headers, locations = get_data(logger, url, email, password, country)
                errors_count = 0

            logger.log("Check available date")
            available_date = get_available_date(url, schedule_id, facility_id, headers)

            book(url, schedule_id, facility_id, '2024-03-01', '14:00', headers)

            if not available_date:
                if logger.debug:
                    logger.log("No dates available")
                elif no_dates_available_count == 20:
                    no_dates_available_count = 0
                    logger.log("No dates available", True)
                else:
                    no_dates_available_count += 1
                time.sleep(3)
            else:
                logger.log("Check available time")
                available_time = get_available_time(url, schedule_id, facility_id, available_date, headers)
                logger.log(f"Nearest: {available_time} {available_date}")

                if (current_date_time is not None and current_date_time
                        <= datetime.strptime(available_time + " " + available_date, "%H:%M %Y-%m-%d")):
                    time.sleep(3)
                    continue

                logger.log("=====================\n"
                           "#                   #\n"
                           "#                   #\n"
                           "#    Try to book    #\n"
                           "#                   #\n"
                           "#                   #\n"
                           f"# {available_time}  {available_date} #\n"
                           "#                   #\n"
                           "#                   #\n"
                           "=====================", True)

                book(url, schedule_id, facility_id, available_date, available_time, headers)

                logger.log("=====================\n"
                           "#                   #\n"
                           "#                   #\n"
                           "#     Booked at     #\n"
                           "#                   #\n"
                           "#                   #\n"
                           f"# {available_time}  {available_date} #\n"
                           "#                   #\n"
                           "#                   #\n"
                           "#  Close window to  #\n"
                           "#    end awaiting   #\n"
                           "=====================", True)

                time.sleep(10)
        except Exception as err:
            headers = None
            if logger.debug:
                logger.log(err)
            elif errors_count % 10 == 0:
                logger.log(err, True)
            errors_count += 1
            time.sleep(min(errors_count, 10) * 3)
            logger.log("Trying again")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
