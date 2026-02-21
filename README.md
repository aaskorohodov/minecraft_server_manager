<!-- TOC -->
* [Features](#features)
  * [Starting with BAT](#starting-with-bat)
  * [Trayer](#trayer)
  * [World backup](#world-backup)
    * [Local receiver](#local-receiver)
  * [Down detector](#down-detector)
* [How to use](#how-to-use)
  * [Windows](#windows)
    * [Getting server ready](#getting-server-ready)
    * [Creating shortcut for windows with poetry](#creating-shortcut-for-windows-with-poetry)
  * [Docker](#docker)
* [Development](#development)
<!-- TOC -->

Minimalistic Manager for Minecraft Sever, designed for Windows

# Features

- Can start Minecraft Server directly or using classic .bat
- Can automatically back up world
- Can automatically clean old backups
- Can send backups to some remote server via HTTP
- Checks if network is available and writes results in locally created DB (uptime counter)

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

- TO_BACKUP – folders with you world to back it up (ABS-Path)
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

You can use this setup on Windows as is, or in Docker with some small adjustments.

## Windows

### Getting server ready

First thing to do is to get server.jar ready, which is Minecraft server itself, the thing this server manager manages.
You will need to download it from mojang and install Java. These things are well described in online.

After doing that you will need to create .bat file to launch server.

1. Pull
2. Create config.env in root of the project
3. Fill config.env as shown in config_example.env
4. Install dependencies with poetry (from pyproject.toml) or with pip (from requirements.txt)
5. Run main.py from virtual environment of your choice


### Creating shortcut for windows with poetry

The main idea is, however, to let Windows manage this app (and therefor minecraft server). To do so, you will need 
to make Windows launch this app on startup automatically, Here how you can do this:

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

With this setup (basically a single shortcut) you will make Windows start server after PC is turned on. I use it this
exact way on dedicated PC. If you do the same way, I also recommend you to set you bios to boot your PC automatically,
which is handy in case your electricity blinks for a moment and PC turns off - BIOS can start you PC whenever power is
on.

## Docker

This app is not well tested in Docker or k8s environment, but if you are going to run this in Docker you will need to:

Check download_server.sh in docker folder. Insert direct link to download required version of Minecraft (like 1.21.10)

```yaml
curl -o /data/server/server.jar \
  https://launcher.mojang.com/v1/objects/<HASH>/server.jar   <- here in download_server.sh
```

DB is only used for down-detector (counts uptime). You can turn it off in settings.py, but if you would like to keep it
running, make sure there is a mount for DB-file (default is sqlite, single file, will be created automatically). DB
will be created at the path, specified in settings.py, so point it to where you want it to be.

**Note: you need DB and files for your world to stay between container restarts, so make sure you mount it somewhere**

Server manager has a setting to launch app from .bat (for Windows) and using command directly. In case of running 
in Docker you will need to launch server directly, to do so keep START_BAT empty in settings.py - app will launch
server.jar (Minecraft server itself) in this case automatically. Also set these settings.py:

- SERVER_DIR 
- TO_BACKUP
- BACKUP_DIR 
- MIN_MEM 
- MAX_MEM 
- DB_PATH

**Note: you can also start server directly (not from .bat) on Windows as well**

Last this is to run Docker with something similar to this:

```bash
docker run -it \
  -p 25565:25565 \
  -v mc-data:/data \
  my-shiny-minecraft-image-name
```

# Development

Before commiting any changes:

```bash
ruff check
```

```bash
poetry lock
poetry export --without-hashes --format=requirements.txt > requirements.txt
```
