
# 🛡️ IPGuardEx - Premium Network & Server Monitor

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.0-8B5CF6?style=for-the-badge&logo=semver&logoColor=white" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Linux-Daemon_Enabled-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux">
</p>

**IPGuardEx** is a professional, high-end automated IP-based server and device status monitoring engine. It features a modern **Aurora Glass-morphism Dashboard Interface** with dedicated tabs for Dashboard, Logs, and Settings. It instantly dispatches live, reliable network failover triggers to your **Telegram** with beautiful, well-structured time formatting (Hours, Minutes, Seconds) and built-in periodic reminders.

Perfect for monitoring **Websites, Routers, Laptops, IP Cameras, Servers**, or any device with an IP address.

## ✨ V2.0.0 Key Features
* 🔥 **Dual Mode Monitoring:** Supports ICMP Ping network checking & active TCP State connection tracking.
* 🛡️ **Crash-Proof Persistence:** If the script or server restarts, it resumes exactly from where it left off. Timers and states never reset!
* ⏱️ **Beautiful Telegram Alerts:** Down/Up notifications display downtime beautifully (e.g., `2 ঘণ্টা 15 মিনিট 30 সেকেন্ড`).
* 🔔 **Smart Alert Delays & Reminders:** Configure delays to avoid false positives, and set custom intervals for down reminders.
* 🗂️ **Tabbed UI Interface:** Clean separation of Dashboard (Live), Logs (History), and Settings (Configuration).
* 📥📤 **Import/Export Targets:** Easily backup and restore your monitoring targets via JSON files directly from the Settings page.
* ♾️ **System Daemon Ready:** Runs 24/7 in the background. Auto-starts on server boot. Immune to terminal closures.
* 🗑️ **One-Click Factory Reset:** Clear all settings, targets, and logs with a single argument (`--clear`).

## 🚀 Installation & Local Deployment Guide

**1. Clone the Repository**
```bash
git clone https://github.com/johirxofficial/IPGuardEx.git
cd IPGuardEx
```

**2. Install Dependencies**
```bash
pip3 install -r requirements.txt
```

**3. First-Time Setup**
Simply run the script. The console will dynamically request environment vectors on the first run:
```bash
python3 index.py
```
*Follow the prompts to enter your Bot Token, Chat ID, Web Name, Port, Alert Delay, and Reminder Interval. After setup, press `Ctrl+C` to stop the script. Your configuration is saved securely in the `.env` file.*

---

## ♾️ Setting Up 24/7 Background Daemon (Linux Systemd)

To ensure the monitor runs forever in the background, starts automatically on server boot, and never stops if you close the terminal, set it up as a Linux service:

**1. Create the Service File**
```bash
sudo nano /etc/systemd/system/ipguardex.service
```

**2. Paste the Configuration** (Replace `johirxofficial` with your actual Linux username and path):
```ini
[Unit]
Description=IPGuardEx Core Monitor Service V2.0.0
After=network.target

[Service]
User=johirxofficial
WorkingDirectory=/home/johirxofficial/IPGuardEx
ExecStart=/usr/bin/python3 /home/johirxofficial/IPGuardEx/index.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=ipguardex

[Install]
WantedBy=multi-user.target
```
*Save and exit: `Ctrl+X`, then `Y`, then `Enter`*

**3. Activate and Start the Daemon**
```bash
# Reload systemd manager configuration
sudo systemctl daemon-reload

# Enable service to start automatically on boot
sudo systemctl enable ipguardex

# Start the service immediately in the background
sudo systemctl start ipguardex
```

**4. Check Service Status & Logs**
* Check if running: `sudo systemctl status ipguardex`
* View live logs: `journalctl -u ipguardex -f`

---

## ⚙️ Management Commands

| Action | Command |
|---|---|
| **Stop Daemon** | `sudo systemctl stop ipguardex` |
| **Restart Daemon** | `sudo systemctl restart ipguardex` |
| **Factory Reset** | `sudo systemctl stop ipguardex` <br> `python3 index.py --clear` <br> `sudo systemctl start ipguardex` |

---

## 🛠️ Built With
* [Python 3](https://www.python.org/) - Core Engine
* [Flask](https://flask.palletsprojects.com/) - Web Dashboard & API
* [Telegram Bot API](https://core.telegram.org/bots/api) - Alert Dispatching

---

Developed with 💻 by [johirxofficial](https://github.com/johirxofficial)

