## ZMQ Rcon for Quake Live Dedicated Server
### Running
Ubuntu/Linux (Python):
0. Clone repository
1. install virtualenv: ```$ virtualenv venv``` or install venv and run ```$ virtualenv venv```
2. activate venv: ```$ source ./venv/bin/activate```
3. install dependencies: ```$ pip install -r requirements.txt```
4. run script: ```$ python zmq_rcon.py --host=tcp://127.0.0.1:28960 --password=pass```


Windows (Python):
1. Install python3+ in your system (ensure you can run python via console or run via direct command like: C:\Python\python)
2. Clone the project to your directory and and cmd.exe in your folder
3. Run via cmd.exe: ```> python -m venv venv```
4. activate virtual environment: ```> .\venv\Scripts\activate```
5. install dependencies: ```> pip install -r requirements.txt```
6. run script: ```> python zmq_rcon.py --host=tcp://127.0.0.1:28960 --password=pass```


Running binary Windows:
```bash
C:\...\Downloads\zmq_rcon.exe --host=tcp://127.0.0.1:28960 --password=password
```

Running binary Ubuntu/Linux:
```bash
$ ./zmq_rcon --host=tcp://127.0.0.1:28960 --password=password
```
