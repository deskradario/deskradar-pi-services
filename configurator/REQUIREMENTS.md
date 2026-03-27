This app is a Pi hosted web app which is used by users of my device to configure it. It should be a super lightweight flask app which focuses on user experience over fancy design. It has 1 main purpose: Provide an interface to the user, with forms, which then triggers off python scripts to perform actions. 

# PHASE 1

I need you to build a fully productionised webapp EXCLUSIVELY in this directory. You DO NOT need any information from outside of this directory in order to complete this tax. Do not read anything outside, do not read the .venv. 

The webapp needs to be based around 2 main modes. 

AP Mode
The PI hosts an AP, and therefore is not connected to the internet. 

LAN Mode.
The Pi is connected to the LAN and therefore DOES have internet. 

You can assume the above statements to always be true, it will always be in one of those modes. The mode can be found at /etc/deskradar-configurator/mode.txt. It'll say AP or LAN. 

The first function of the webapp will be to swtich between these modes. You must create 2 independant python scripts which use nmcli to adjust the network configuration of the pi. These scripts should be runnable independant of the web app, and use command line arguments to work. The two scripts will be "swtich_to_lan.py" and "switch_to_ap.py"

switch_to_lan.py
The webpage will contain an ssid and password box
When run, providing both boxes have content, the webapp will fire off a script which lowers the AP, configures a new WiFi connection, then joins it. 

switch_to_ap.py
Will delete the profile which switch_to_lan.py made if it exists, (it can have a set name) and then raise the pre-configured AP. You should get the name of the AP from the .env file, and you can use "piAP" as a first value - as in, put this in your env. It should not be a default. 

Once you have configured the app to do this, so I can open the page via my phone and connect to the webapp via deskradar.local, and freely switch between each mode. 

The logs should go to stdOUT.


## Code Preference
Use HTML, CSSS and Python. Nothing else. Keep the stack SUPER simple. This just needs to fucking work and be robust.


# Phase 2
The second usecase of this app will be to update the values of a settings file found at /etc/deskradar/config.json. 
Read the config.json file in this repo, as an example, and implement a script and web page which allows the user to input new values and update this file. Once complete, run sudo systemctl restart deskradar.