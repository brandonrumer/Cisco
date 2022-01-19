#!/usr/local/bin/python3
""" Summary: Connects to devices and runs a command or set of commands.

Description:
    Asks the user whether they want to import a CSV for IPs to work on,
    or whether an IP range should be manually entered. Then this script
    connects to each device and runs a user-inputted command. The output
    is captured and exported to a CSV.

    Multithreading is used so that multiple devices can be configured at
    the same time. The user is asked how many threads are to be used so
    the python-hosted computer or network isn't saturated.
"""

__author__ = "Brandon Rumer"
__version__ = "2.0.0"
__email__ = "brumer@cisco.com"
__status__ = "Production"


""" Importing built-in modules """
import csv
import datetime
import getpass
import ipaddress
import os
# import socket
import subprocess
import sys
# import tempfile
import threading
import time
from queue import Queue
import re
# from multiprocessing.pool import ThreadPool
import tkinter as tk
from tkinter import filedialog

""" Import external modules """
from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)


def ConnectIPs(startipInt, endipInt):
    """ Collects the IPs in the range the user specified  """
    IPs = []
    if startipInt == endipInt:
        i = ipaddress.IPv4Address(startipInt)
        IPs.append(str(i))
        return IPs
    else:
        start_ip = ipaddress.IPv4Address(startipInt)
        end_ip = ipaddress.IPv4Address(endipInt)
        for ip_int in range(int(start_ip), int(end_ip)):
            i = ipaddress.IPv4Address(ip_int)
            IPs.append(str(i))
        return IPs


def ssh_exec_command(commands, host, user, pw, user_timeout, output_q):
    """ SSH to the device, send commands, and capture the output """
    output = ''
    output_list = {}

    cisco_device = {
        'device_type': 'cisco_ios',
        'host': host,
        'username': user,
        'password': pw,
        'secret': pw
    }

    try:
        try:
            # Set up SSH session
            with ConnectHandler(**cisco_device) as ssh:
                ssh.enable()

                print('')
                print('_____________________________________________________________')
                print('')
                print('Connection established to', host)
                print('_____________________________________________________________')

                hostname = ssh.find_prompt()
                print('Hostname of device: ', hostname)

                '''
                # Check if connected in user mode and enter enable mode
                if not conn.check_enable_mode():
                    conn.enable()
                '''

                for command in commands:
                    # send_command waits for the prompt vs send_command_timing is time-based
                    # output = ssh.send_command(command)

                    # Doing a lot of work here to detect a question, but not freeze up if there's not
                    output = ssh.send_command(
                        command,
                        expect_string=r"([#\?$>])",
                        delay_factor=10,
                        max_loops=1000)

                    if ('[' in output) and (']' in output) and ('?' in output):
                        output += ssh.send_command(
                            '\n',
                            expect_string=r"([#\?$>])",
                            delay_factor=10,
                            max_loops=1000)

                    output_list[command] = output
                    print('On ', host, ', done with command: ', command)

                # Put gathered info into a row
                output_list = [host, output]
                print('Adding this to report:', output_list)
                output_q.put([output_list])

                # Cleanup SSH
                ssh.disconnect()
                print('Closing SSH')

        except IndexError:
            pass
        except ConnectionRefusedError as err:
            print(f"Connection Refused: {err}")
            output_list = [host, 'Connection Refused']
            output_q.put([output_list])
        except TimeoutError as err:
            print(f"Connection Refused: {err}")
            output_list = [host, 'SSH Timeout']
            output_q.put([output_list])
        except Exception as err:
            print(f"Oops! {err}")
            output_list = [host, 'Error']
            output_q.put([output_list])
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as error:
            print(f"{error} on {host}")

    except KeyboardInterrupt:
        print('\n Detected keyboard interrupt. Exiting thread.')
        ssh.disconnect()
        threadLimiter.release()

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

    print('\n')
    print('Would you like to import a CSV for IPs to work on, or manually')
    print('enter an IP range?')
    print('')
    print('Please choose:')
    print('Press "1" to specify an IP range')
    print('Press "2" to specify a CSV of IPs')
    print('')
    try:
        IPSource = input('Press 1 or 2: ')
        if (IPSource == '1'):
            print('')
            return IPSource
        elif (IPSource == '2'):
            return IPSource
        else:
            print('Syntax Error!')
            print('\n')
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
        CommandNumber = int(input('How many commands (lines) do you want to run: '))
    except ValueError:
        print('Input a number!')
        CommandNumber = ''
        CommandNumber = NumberOfCommands()
    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        sys.exit(0)
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
            MaxThreads()


def CommandSource():
    """ Ask if user-entered commands or a text file of configuration should be used """
    print('' * 3)
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
        print('var: ', CommandsourceVar)
        sys.exit(0)
        CommandSource()


if __name__ == "__main__":

    # Clearing anything so we get a clean run
    counter = 0
    results = []
    my_dict = []
    output_q = Queue()
    user_timeout = 10000

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
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('\n' * 1)
    print('Please note: if "[yes or no]" is detected in the same line, this script will choose yes. If the')
    print('script asks for additional input, and "[" and "]" are detected in the same line (without')
    print('yes or no) , this script will assume that the device is asking for input. The default value will be')
    print('chosen. If this is not acceptable then this script may not be suitable for the command.')
    print('\n' * 1)
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('\n' * 1)
    time.sleep(3)

    # Ask the user what the souce is for devices
    try:
        IPSource = UserSelect()
        if IPSource == '1':
            startipInt = input('Starting IP: ')
            endipInt = input('Ending IP: ')
            IPs = ConnectIPs(startipInt, endipInt)

        elif IPSource == '2':
            print('CSV file should have only one column with only IPs in a single column.')
            print("Loading Windows File Explorer (if it doesn't show up check behind this terminal).")
            time.sleep(1)
            IPs = []
            somecsvfile = tk.Tk()
            somecsvfile.withdraw()
            filename = filedialog.askopenfilename()
            print(filename)

            with open(filename, 'r') as infile:
                reader = csv.reader(infile)
                IPs = [rows[0] for rows in reader]

    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        sys.exit(0)

    # Ask if user-entered commands or a text file of configuration should be used
    commands = []
    CommandSourceVar = CommandSource()
    if CommandSourceVar == '1':
        # Ask how many commands to run
        print('')
        CommandNumber = NumberOfCommands()
        while CommandNumber > 0:
            print('CommandNumber: ', CommandNumber)
            command = input('What command do you want to run: ')
            commands.append(command)
            CommandNumber = CommandNumber - 1

    elif CommandSourceVar == '2':
        print("Loading Windows File Explorer (if it doesn't show up check behind this terminal).")
        commandfile = tk.Tk()
        commandfile.withdraw()

        commandfilename = filedialog.askopenfilename()
        print('Using this file for device configuration: ', commandfilename)
        with open(commandfilename) as f:
            commands = f.readlines()
        commands = [x.strip() for x in commands]
        CommandNumber = len(commands)
    print('commands: ', commands)

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
        host = host.replace(' ', '')
        try:
            threadLimiter.acquire()
            my_thread = threading.Thread(target=WorkIt, args=(commands, host, user, pw, user_timeout, output_q))
            my_thread.start()
        except KeyboardInterrupt:
            print('\n Fine. Exiting')
            sys.exit(0)

    # Wait for threads to complete
    main_thread = threading.current_thread()
    for some_thread in threading.enumerate():
        if some_thread != main_thread:
            some_thread.join()

    # Defining date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    # Specifying the CSV export filename
    csvExport = 'results-{}.csv'.format(timestamp)
    writer = csv.writer(open(csvExport, 'w', newline=''))
    writer.writerow(['Host', 'Results'])

    # Get everything from the queue
    while not output_q.empty():
        my_dict = output_q.get()
        for datastuff in my_dict:
            writer.writerow(datastuff)

    print('\n' * 3)
    print('Results saved as:', csvExport)
    print('\n')
    print("        Hint: Don't see all the devices?")
    print("              Maybe the device failed the ping test.")
    print('\n' * 2)
