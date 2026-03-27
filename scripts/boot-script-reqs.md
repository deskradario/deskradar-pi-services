Create a script which does the following. This script will run once on every boot to make sure the device is working correctly.

The script should:

Wait until a CIRCUITPYTHON device is connected via USB. It will always bare that name but occasionally gets CIRCUITPYTHON2, 3 or 4. Only one will ever actually be connected, so wait until one is before continuing.
- If none show up for 15s, log the error and reboot the device 5s after the log. 

Once up, read ip.txt from the filesystem, validate it's a fully formed ipv4 address and then write to the "MATRIX_HTTP_URL" key at /etc/deskradar/config.json. Validate this path exists, and create it if it doesnt. 

Then exit.