# Usa VISA appointment bot for [AIS](https://ais.usvisa-info.com/) region

Use this bot on your own risk

## Requirements

- python >= 3.10 (Wasn't tested on python < 3.10)

## Download .exe

[Download](https://github.com/aigrvch/USA-VISA-Bot/releases)

## Usage

```sh
pip install -r requirements.txt
python main.py
```

## Build exe

```sh
pip install pyinstaller
pyinstaller -F main.py
```

## FAQ and recommendations

1. Delete file `config` to reset configuration.
2. Bot may use up the number of attempts to write to the consul, so:
    - check attempts on official website
    - carefully set the maximum and minimum interview dates
3. Bot has ASC registration, but it may not work. Make pull request, if you fixed it
4. Join [Telegram group](https://t.me/u_s_a_visa_bot)