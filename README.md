<!-- TOC -->
* [How to use](#how-to-use)
  * [Creating shortcut for windows with poetry](#creating-shortcut-for-windows-with-poetry)
* [Before commiting](#before-commiting)
<!-- TOC -->

Minimalistic Manager for Minecraft Sever, designed for Windows

# Features

- Can start Minecraft Server directly or using classic .bat
- Can automatically back up world
- Can automatically clean old backups
- Can send backups to some remote server via HTTP
- Checks if network is available and writes results in locally created DB

## Starting with BAT

To start server you can use .bat-file. You can read about starting server with bat online, but in general you need to
create start.bat with something similar to this:

```bat
@ECHO OFF
java -Xms2G -Xmx8G -jar server.jar
Pause
```

Set up Xms and Xmx (min and max RAM) as you like.

After installing dependencies with pip or poetry, all you have to do is append path to this .bat file to config.env as
abs-path and run main.py

## Trayer

On start up you app will create an icon in tray with buttons:

- Info – will show errors if any
- Restart - will restart server and app
- BackUp - will back up world immediately
- NetStat - will show network availability record for the last 24 hours

## World backup

This manager will attempt to copy world, making backup. To do so, you will need to include in config.env:

- WORLD_DIR – folder with you world to back up it (ABS-Path)
- BACKUP_DIR – where to back up world
- BACKUP_TIME – when to back up world
- BACK_UP_DAYS – how many days to store backups (any backups older will be deleted automatically)
- WORLD_SENDER_ON – if set to true, app will attempt to send backup to remote server of your choice
- SEND_ATTEMPTS – attempts to send backup
- RECEIVER_IP – IP of the receiver to send backup to
- RECEIVER_PORT – port of the receiver to send backup to
- RECEIVER_TOKEN – token for basic auth to connect to receiver
- RECEIVER_DIR – in case local receiver is selected, this would be ABS-path to save received backup to

App will turn off server while making backup, and then turn it on again automatically, even if case backup failed.
If you set it up to send backup to some remote server, app will do so in background, so server will be off only 
while backup is copied and zipped.

### Local receiver

There is small app that can be run in parallel with main app, that plays a role of the receiver. This app will create
http-server and start listening on specified port. To start this additional app, execute file_transfer->receiver.py
This is a completely separate app, an example of what receiver might look like.

Use case is:
- You launch minecraft-server on one PC
- You launch receiver on second PC (probably in the same network, not to expose receiver online)
- You send backup from one PC to another

Receiver uses the same logic to delete old backups

## Down detector

App have a built-in network-detector. You can turn it on\off with config.env by using DETECTOR_ON=True\False

If on, detector will make http-requests to addresses, provided in CONNECTIVITY_URLS. If any responded, detector will 
assume that network is available, so it will save result as "on". If server is off, detector will try to
write down "off" status before turning off.

You can check statistics by directly accessing locally created DB (sqlite), by using button in tray or by running 
plot_drawer.py. In case using trayer or plot_drawer.py you will get a graph with on-off time.

When writing to DB, down-detector will only write change in status. This is to reduce DB size

# How to use

1. Pull
2. Create config.env in root of the project
3. Fill config.env as shown in config_example.env
4. Install dependencies with poetry (from pyproject.toml) or with pip (from requirements.txt)
5. Run main.py from virtual environment of your choice

## Creating shortcut for windows with poetry

1. Locate your executable (python.exe) in poetry's virtual environment
2. Set ABS-path to executable into shortcuts target and ABS-path to main.py as argument, like so:
```
C:\Users\...\Scripts\python.exe "C:\Users\...\main.py"
```
3. Set ABS-path to Scripts-folder with executable into 'Start in' for shortcut:
```
C:\Users\...\Scripts
```
4. Press Win+R type 'shell:startup'
5. Place shortcut that you created into this folder

# Before commiting

```bash
ruff check
```

```bash
poetry lock
poetry export --without-hashes --format=requirements.txt > requirements.txt
```
