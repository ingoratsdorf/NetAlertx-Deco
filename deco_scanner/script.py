#!/usr/bin/env python



async def main():
    session = aiohttp.ClientSession()
    test=deco.TplinkDecoApi(session,'http://192.168.1.254', 'admin', 'Z29i*98%w9^lkXMNbV',False, 2, 30)

    print("\n##################\nList of DECOs:\n")
    devices = await test.async_list_devices()        
    print(json.dumps(devices, indent=3))

    print("\n##################\nList of Clients:\n")
    clients = await test.async_list_clients()
    print(json.dumps(clients, indent=3))

asyncio.run(main())




from __future__ import unicode_literals
import pathlib
import subprocess
import argparse
import os
import sys
import chardet  

import asyncio
import json
import TplinkDecoApi.api as deco
import TplinkDecoApi.exceptions

# install with "pip install aiohttp"
import aiohttp

# Register NetAlertX directories
INSTALL_PATH="/app"
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Object, Plugin_Objects, handleEmpty, is_mac
from logger import mylog
from helper import timeNowTZ, get_setting_value 
import conf
from pytz import timezone

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

CUR_PATH = str(pathlib.Path(__file__).parent.resolve())
LOG_FILE = os.path.join(CUR_PATH, 'script.log')
RESULT_FILE = os.path.join(CUR_PATH, 'last_result.log')


pluginName= 'DECODS'

# -------------------------------------------------------------
def main():    
    mylog('verbose', [f'[{pluginName}] In script'])
    last_run_logfile = open(RESULT_FILE, 'a')
    last_run_logfile.write("")

    parser = argparse.ArgumentParser(description='Import clients from a DECO network')
    parser.add_argument('paths',  action="store",  help="absolute dhcp.leases file paths to check separated by ','")
    values = parser.parse_args()

    plugin_objects = Plugin_Objects(RESULT_FILE)

    if values.paths:
        for path in values.paths.split('=')[1].split(','): 
            plugin_objects = get_entries(path, plugin_objects)
            mylog('verbose', [f'[{pluginName}] {len(plugin_objects)} Entries found in "{path}"'])        
            
    plugin_objects.write_result_file()

# -------------------------------------------------------------
def get_entries(path, plugin_objects):

    # Check if the path exists
    if not os.path.exists(path):
        mylog('none', [f'[{pluginName}] ⚠ ERROR: "{path}" does not exist.'])
    else:
        # Detect file encoding
        with open(path, 'rb') as f:
            result = chardet.detect(f.read())

        # Use the detected encoding
        encoding = result['encoding']

        # Order: MAC, IP, IsActive, NAME, Hardware 
        # Handle pihole-specific dhcp.leases files
        if 'pihole' in path:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                for line in f:
                    row = line.rstrip().split()
                    if len(row) == 5:
                        plugin_objects.add_object(
                            primaryId   = handleEmpty(row[1]),
                            secondaryId = handleEmpty(row[2]),
                            watched1    = handleEmpty('True'),
                            watched2    = handleEmpty(row[3]),
                            watched3    = handleEmpty(row[4]),
                            watched4    = handleEmpty('True'),
                            extra       = handleEmpty(path),
                            foreignKey  = handleEmpty(row[1])
                        )
        elif 'dnsmasq' in path:
            # [Lease expiry time] [mac address] [ip address] [hostname] [client id, if known]
            # e.g.
            # 1715932537 01:5c:5c:5c:5c:5c:5c 192.168.1.115 ryans-laptop 01:5c:5c:5c:5c:5c:5c
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                for line in f:
                    row = line.rstrip().split()
                    if len(row) > 3:
                        plugin_objects.add_object(
                            primaryId   = handleEmpty(row[1]),
                            secondaryId = handleEmpty(row[2]),
                            watched1    = handleEmpty('True'),
                            watched2    = handleEmpty(row[3]),
                            watched3    = '',
                            watched4    = handleEmpty('True'),
                            extra       = handleEmpty(path),
                            foreignKey  = handleEmpty(row[1])
                        )
        else:
            #  Handle generic dhcp.leases files
            leases = DhcpLeases(path)
            leasesList = leases.get()
            for lease in leasesList:

                # filter out irrelevant entries (e.g. from OPNsense dhcp.leases files)
                if is_mac(lease.ethernet):

                    plugin_objects.add_object(
                        primaryId   = handleEmpty(lease.ethernet),    
                        secondaryId = handleEmpty(lease.ip),  
                        watched1    = handleEmpty(lease.active),   
                        watched2    = handleEmpty(lease.hostname),
                        watched3    = handleEmpty(lease.hardware),
                        watched4    = handleEmpty(lease.binding_state),
                        extra       = handleEmpty(path),
                        foreignKey  = handleEmpty(lease.ethernet)
                    )
    return plugin_objects

if __name__ == '__main__':    
    main()  