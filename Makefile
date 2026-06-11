.PHONY: setup test test-setup test-bot run clean install service

# Python virtual environment
VENV = venv
PYTHON_VERSION = python3.13
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Setup virtual environment and install dependencies
setup: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	$(PYTHON_VERSION) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV)/bin/activate

# Install test dependencies
test-setup: setup
	$(PIP) install -r tests/requirements.txt

# Run tests
test: test-setup
	$(PYTHON) -m pytest tests/ -v --timeout=30

# Run legacy bot test
test-bot: setup
	$(PYTHON) test_bot.py

# Run the bot
run: setup
	$(PYTHON) telegram_kiro_bot.py

# Install as user systemd service
install:
	mkdir -p ~/.config/systemd/user
	cp telegram-kiro-bot.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable telegram-kiro-bot

# Start/stop service
service-start:
	systemctl --user start telegram-kiro-bot

service-stop:
	systemctl --user stop telegram-kiro-bot

service-status:
	systemctl --user status telegram-kiro-bot

service-logs:
	journalctl --user-unit telegram-kiro-bot -f

# Clean up
clean:
	rm -rf $(VENV)
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
