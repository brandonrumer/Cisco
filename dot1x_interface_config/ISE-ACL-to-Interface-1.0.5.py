#!/usr/local/bin/python3
""" Summary: Reports config on access interfaces, which have specific VLANs.

Description:
    Asks the user whether they want to import a CSV for IPs to work on,
    or whether an IP range should be manually entered. Then this script
    connects to each device and checks the interface configuration. The
    device, and resulting interface config is is captured and exported
    to a CSV.

    Multithreading is used so that multiple devices can be configured at
    the same time. The user is asked how many threads are to be used so
    the python-hosted computer or network isn't saturated.

Future:
    -If a specific VLAN is allowed on an access/edge interface then the
    appropriate config is applied.
    -Import a list of VLANs to check for.
"""

__author__ = "Brandon Rumer"
__version__ = "1.0.5"
__email__ = "brumer@cisco.com"
__status__ = "Production"


""" Importing built-in modules """
import csv
import socket
import argparse
import sys
import tempfile
import datetime
import time
import os
import getpass
import re
import subprocess
import threading
from queue import Queue
from multiprocessing.pool import ThreadPool
import ipaddress
import tkinter as tk
from tkinter import filedialog
import json

""" Import external modules """
from netmiko import Netmiko, file_transfer
from paramiko.ssh_exception import SSHException
import requests
from orionsdk import SwisClient
from ciscoconfparse import CiscoConfParse


def ConnectIPs(startipInt, endipInt):
    """ Collects the IPs in the range the user specified  """
    IPs = []
    start_ip = ipaddress.IPv4Address(startipInt)
    end_ip = ipaddress.IPv4Address(endipInt)
    for ip_int in range(int(start_ip), int(end_ip)):
        i = ipaddress.IPv4Address(ip_int)
        IPs.append(str(i))
    return IPs


def ssh_exec_command(commands, host, user, pw, user_timeout, output_q):
    """ SSH to the device, sshsend commands, and capture the output

    Output:
        {'Host': '1.1.1.1', 'Hostname': 'Router', 'Interfaces': {'interface Gi1/1': ['int line 1', 'line 2'...]}}

    """
    time.sleep(1)
    ssh_error = 'SSH Error'

    output = ''
    output_list = []  # One per device
    keys = ['Host', 'Hostname', 'Interfaces']
    device_dict = {key: None for key in keys}
    Interfaces = {}
    output_dict = {}

    try:
        try:

            # Set up SSH session
            device = {
                'device_type': 'cisco_ios',
                'host': host,
                'username': user,
                'password': pw,
            }
            device_dict.update(Host=host)

            ssh = Netmiko(**device)

            print('')
            print('_____________________________________________________________')
            print('')
            print('Connection established to', host)
            print('_____________________________________________________________')

            time.sleep(5)

            # Get the router/switches prompt. This will be used later to see if the commands are done.
            deviceprompt = ssh.find_prompt()  # NetMiko: find device prompt
            device_dict.update(Hostname=deviceprompt)

            ssh.send_command(
                'terminal length 0\n'
            )

            # print('COMPLETE: terminal length 0')

            # The string below doesn't work on slow or large stacks, so using send_command_timing instead
            ''' #  The below doesn't work
            runningconfig = ssh.send_command(
               'sh run | sec interface\n',
                expect_string=r'#'
            )
            '''

            #######################################################
            ###### COMMAND WE WANT TO LOOK AT THE OUTPUT FOR ######
            #######################################################

            runningconfig = ssh.send_command_timing(
                'sh run | sec interface\n',
                delay_factor=10  # This number * 2 seconds
            )

            print('COMPLETE: sh run | sec interface')
            print('working on output...')

            runningconfig = runningconfig.splitlines()
            parse = CiscoConfParse(runningconfig)

            ####################################################################
            # Find access interfaces. Filter out any interface that has access #
            #  AND trunk since it's possible to have both config lines.        #
            ####################################################################

            # Look for interfaces that do not have trunk in their config
            for i in (parse.find_objects_wo_child(r'^interface', r'trunk')):
                intvalues = []
                # Look for interfaces, that do not have trunk, but have switchport access vlan
                for vlannum in commands:
                    accessvlan = 'switchport access vlan {}'.format(vlannum)
                    access_interface = i.has_child_with(accessvlan)
                    if access_interface is True:
                        break

                if access_interface is True:
                    for line in i.all_children:
                        intvalues.append(line.text)
                    Interfaces[i.text] = intvalues  # {'int gi1/1: [conf line 1, line2 ...]}
                device_dict.update(Interfaces=Interfaces)  # put interfaces in device's dict

            # Send output to the main program where it can be dumped to an output file
            print('Adding this to report:', device_dict)
            output_q.put(device_dict)

            # Cleanup SSH
            ssh.disconnect()

        except IndexError:
            pass
        except SSHException:
            print('SSH error on', host)

        except KeyboardInterrupt:
            print('\n Keyboard interrupt detected. Exiting thread.')
            try:
                ssh.disconnect()
            except Exception:
                pass

    except KeyboardInterrupt:
        print('\n Keyboard interrupt detected. Exiting thread.')
        try:
            ssh.disconnect()
        except Exception:
            pass

    finally:
        threadLimiter.release()


def check_pingv2(host):
    """ Checks to see if the IP address responds to a single ping.  """
    with open(os.devnull, 'w') as DEVNULL:
        try:
            subprocess.check_call(
                ['ping', '-n', '4', host],
                stdout=DEVNULL,
                stderr=DEVNULL
            )
            pingstatus = True
        except subprocess.CalledProcessError:
            pingstatus = False
    return pingstatus


def WorkIt(commands, host, user, pw, user_timeout, output_q):
    """ Placeholder function, primarily needed for multithreading  """
    pingstatus = check_pingv2(host)
    if pingstatus is True:
        ssh_exec_command(commands, host, user, pw, user_timeout, output_q)
    elif pingstatus is False:
        threadLimiter.release()


def UserSelect():
    """ Summary: Asks user if a CSV or manually-entered IP list should be used.

    Description:
        Asks the user whether they want to import a CSV for IPs to work on,
        or whether an IP range should be manually entered.
    """

    print('\n' * 2)
    print('Would you like to import a CSV for IPs to work on, or manually')
    print('enter an IP range?')
    print('')
    print('Please choose:')
    print('Press "1" to specify an IP range')
    print('Press "2" to specify a CSV of IPs')
    print('Press "3" to use SolarWinds')
    print('')
    try:
        IPSource = input('Press 1 or 2 or 3: ')
        if (IPSource == '1'):
            print('')
            return IPSource
        elif (IPSource == '2'):
            # print('sleeping for 2 seconds...')
            # time.sleep(2)
            return IPSource
        elif (IPSource == '3'):
            print('')
            return IPSource
        else:
            print('Syntax Error!')
            print('\n' * 5)
            UserSelect()
    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        sys.exit(0)


def NumberOfCommands():
    """ Asks the user to input a number between 1-9 """
    try:
        if CommandNumber >= 1:
            return CommandNumber
    except:
        pass
    try:
        CommandNumber = int(input('How many different access vlans do you want to look for? '))
    except ValueError:
        print('Input a number!')
        CommandNumber = ''
        CommandNumber = NumberOfCommands()
    if CommandNumber == 0:
        print('Zero is not a valid entry')
        CommandNumber = NumberOfCommands()
    elif CommandNumber > 9:
        print('For the saftely of the environment this is limited to 9 or less')
        CommandNumber = NumberOfCommands()
    return CommandNumber


def MaxThreads():
    """ Summary: Maximum threads

    Description:
        User-customizable number of maximum threads to spawn when connecting
        to devices. This is useful so the machine and network are not
        over-utilized when running the script.

    Parameters:
        BoundedSephamore()

    Default:
        BoundedSephamore(100)
    """

    threads = input('Max concurrent devices do you want to connect to (default 100): ')
    if threads == '':
        threads = int('100')
        return threads
    else:
        try:
            number = int(threads)
            return number
        except ValueError:
            print('Only input numeric numbers!')
            print('')
            Maxthreads()


def solarwinds_query(npm_server, username, password):
    verify = False
    if not verify:
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    swis = SwisClient(npm_server, username, password)
    node_results = swis.query("SELECT IPAddress from Orion.Nodes n where n.Vendor = 'Cisco'")
    return node_results


def SolarwindsIP(var):
    for devices in node_results['results']:
        #  For devices in var:
        return devices['IPAddress']


def CommandSource():
    """ Ask if user-entered commands or a text file of configuration should be used """
    print('' * 2)
    print('Do you want to type the commands to be ran on remote hosts, or use a')
    print('line-by-line text file of configuration?')
    print('')
    print('Type "1" for manually typing commands, or')
    print('Type "2" for importing a file of commands.')
    print('')
    CommandSourceVar = input('Press 1 or 2: ')
    if (CommandSourceVar == '1') or (CommandSourceVar == '2'):
        return CommandSourceVar
    else:
        print('Syntax Error!')
        print('\n' * 3)
        print('var: ', CommandSourceVar)
        quit(0)
        CommandSource()


if __name__ == "__main__":
    # Clearing anything so we get a clean run
    counter = 0
    results = []
    my_dict = []
    output_q = Queue()
    user_timeout = 10

    # Defining date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    print('\n' * 20)  # May not want to clear screen, so just putting a bunch of blank lines
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('/////////////////////////////   /////////////////////////////////   ///////////////////////////////')
    print('/////////////////////////////   /////////////////////////////////   ///////////////////////////////')
    print('/////////////////////////////   /////////////////////////////////   ///////////////////////////////')
    print('////////////////////  .//////   //////  .///////////////. .//////   //////.  //////////////////////')
    print('////////////////////   //////   //////   ///////////////   //////   //////   //////////////////////')
    print('////////////*///////   //////   //////   ///////*///////   //////   //////   ///////*//////////////')
    print('///////////   //////   //////   //////   //////   //////   //////   //////   //////   /////////////')
    print('///////////   //////   //////   //////   //////   //////   //////   //////   //////   /////////////')
    print('///////////   //////   //////   //////   //////   //////   //////   //////   //////   /////////////')
    print('/////////////////////////////   /////////////////////////////////   ///////////////////////////////')
    print('/////////////////////////////* /////////////////////////////////// ////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('//////////////////////     *////   *//////.    .////////,    .////////     ////////////////////////')
    print('///////////////////        .////   *////        /////*        /////           /////////////////////')
    print('//////////////////    //////////   *////   ,////////.   ./////////    /////    ////////////////////')
    print('/////////////////,   ///////////   *////*      .////    /////////*   ///////   *///////////////////')
    print('//////////////////   ,//////////   *////////.    ///    //////////   */////,   ////////////////////')
    print('//////////////////.     .  .////   *////,///*    ////      .  ////,           ,////////////////////')
    print('////////////////////.      .////   *////       ,///////       //////.       .//////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('\n' * 3)
    time.sleep(1)

    # Ask the user what the souce is for devices
    try:
        IPSource = UserSelect()
        if IPSource == '1':
            startipInt = input('Starting IP: ')
            endipInt = input('Ending IP: ')
            IPs = ConnectIPs(startipInt, endipInt)

        elif IPSource == '2':
            print('CSV file should have only one column with only IPs in a single column.')
            time.sleep(1)
            IPs = []
            somecsvfile = tk.Tk()
            somecsvfile.withdraw()
            filename = filedialog.askopenfilename()
            print(filename)

            with open(filename, 'r') as infile:
                reader = csv.reader(infile)
                IPs = [rows[0] for rows in reader]

        elif IPSource == '3':
            IPs = []
            # Define solarwinds creds and connection settings
            npm_server = input('Enter IP for SolarWinds NPM: ')
            # npm_server = ''
            username = input('Enter username to connect with: ')
            password = getpass.getpass("Enter password: ")
            # password = ''

            # Poll SolarWinds for data
            node_results = solarwinds_query(npm_server, username, password)
            var = node_results['results']

            for IP in var:
                IPs.append(IP['IPAddress'])
    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        exit(0)

    # Ask if user-entered commands or a text file of configuration should be used
    commands = []
    '''
    CommandSourceVar = CommandSource()
    if CommandSourceVar == '1':
        # Ask how many commands to run
        print('')
        CommandNumber = NumberOfCommands()
        while CommandNumber > 0:
            print('CommandNumber: ' , CommandNumber)
            command = input('What command do you want to run: ')
            commands.append(command)
            CommandNumber = CommandNumber-1

    elif CommandSourceVar == '2':
        commandfile = tk.Tk()
        commandfile.withdraw()

        commandfilename = filedialog.askopenfilename()
        print('Using this file for device configuration: ' , commandfilename)
        with open(commandfilename) as f:
            commands = f.readlines()
        commands = [x.strip() for x in commands]
        #commands = [x.strip() for x in content]
        CommandNumber = len(commands)
        print('commands: ' , commands)
    '''

    # Ask what VLANs we want to look for
    print('\n')

    print('Would you like to look for a particular set of access VLANs? "y" or "n"')
    specifyvlan = input('(If you want to search for just access ports, without a specific VLAN, type "n"): ')
    specifyvlan = str.lower(specifyvlan)
    if specifyvlan == 'y':
        print('\n')
        CommandNumber = NumberOfCommands()  # For code reuse purposes, the CommandNumber var is really VLAN operations
        while CommandNumber > 0:
            print('\n')
            command = input('What access vlan are you looking for: ')  # Command variable is holding vlans
            commands.append(command)
            CommandNumber = CommandNumber - 1
    else:
        command = ''

    # Get credentials for devices & setting some variables
    print('\n' * 2)
    print('Enter username to connect with.')
    user = input('(typically, the domain is not needed): ')
    print('')
    pw = getpass.getpass("Enter password: ")
    print('\n' * 2)

    # Ask user how many threads they want to spawn
    threads = MaxThreads()
    threadLimiter = threading.BoundedSemaphore(threads)

    # Do the work, while limiting the number of threads
    for host in IPs:
        try:
            threadLimiter.acquire()
            my_thread = threading.Thread(target=WorkIt, args=(commands, host, user, pw, user_timeout, output_q))
            my_thread.start()
        except KeyboardInterrupt:
            print('\n Fine. Exiting')
            exit(0)

    # Wait for threads to complete
    main_thread = threading.currentThread()
    for some_thread in threading.enumerate():
        if some_thread != main_thread:
            some_thread.join()

    dataexport = 'results-{}.json'.format(timestamp)
    information = []

    # Get everything from the queue and add to a dictionary
    while not output_q.empty():
        my_dict = output_q.get()
        information.append(my_dict.copy())

    # Dump the dictionary to a JSON file
    with open(dataexport, 'w') as my_data_file:
        json.dump(information, my_data_file)

    print('\n' * 5)
    print('Results saved as:', dataexport)
    print('\n' * 3)
