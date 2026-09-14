test:
    python3 -m unittest discover -s tests -v
    python3 -m unittest discover -s ld-mac-prepare-native/tests -v
    python3 -m unittest discover -s hermes-uber-ride-agent/tests -v
    python3 -m unittest discover -s hermes_browser_booking_no_api/tests -v

help:
    python3 -m coffee_work.cli --help
