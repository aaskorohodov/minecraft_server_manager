<!-- TOC -->
* [How to use](#how-to-use)
  * [Creating shortcut for windows with poetry](#creating-shortcut-for-windows-with-poetry)
* [Before commiting](#before-commiting)
<!-- TOC -->

Minimalistic Manager for Minecraft Sever, designed for Windows

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
