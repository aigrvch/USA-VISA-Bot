# Usa VISA appointment bot for [AIS](https://ais.usvisa-info.com/) region

## Requirements

- python >= 3.10 (Wasn't tested on python < 3.10)

## Usage

```sh
pip install -r requirements.txt
python main.py
```

Bot will ask email, password and country for login in system

## Build exe

```sh
pip install pyinstaller
pyinstaller -F main.py
```