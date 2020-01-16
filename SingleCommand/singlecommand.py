#!/usr/local/bin/python3
""" Summary: Connects to multiple devices and runs a command.

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
__version__ = "1.4.1a"
__email__ = "brumer@cisco.com"
__status__ = "Production"


""" Importing built-in modules """
import argparse
import csv
import datetime
import getpass
import ipaddress
import os
import re
#import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from queue import Queue
from multiprocessing.pool import ThreadPool
import tkinter as tk
from tkinter import filedialog

""" Import external modules """
import paramiko
import requests
from orionsdk import SwisClient # Solarwinds plugin

'''
def handler(signum, frame):
    print('\n Fine. Exiting')
    exit(0)
'''

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
    """ SSH to the device, send commands, and capture the output """
    output = ''
    output_list = []
    ssh_error = 'SSH Error'
    try:
        try:
            # Set up SSH session
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=user, password = pw)
            print('')
            print('_____________________________________________________________')
            print('')
            print('Connection established to' , host)
            print('_____________________________________________________________')
            # Open Shell
            remote_shell = ssh.invoke_shell()
            #output = remote_shell.recv(10000)
            time.sleep(3)

            # Clear Output (banner)
            if remote_shell.recv_ready():
                output = remote_shell.recv(10000)
                # Get the router/switches prompt. This will be used later to see if the commands are done.
                deviceprompt = output.decode('ascii').rsplit('\n' , 1)[1]
                #print('device prompt var: ' , deviceprompt)

            CountOfCommands = len(commands)

            for i in commands:
                deviceoutput = ''
                cell = CountOfCommands+1 #CountOfCommands is the count, not the iteration currently on
                # print('Output put in column ' , cell)
                # Send the command
                sendIt = '{}\n'.format(i)
                remote_shell.send(sendIt)
                time.sleep(2)

                ''' Capture the screen, insuring that the command is done executing. '''
                output = CaptureScreen(remote_shell, deviceprompt)
                #print('Done with command number ' , cell)
                print('On ' , deviceprompt , ', done with command: ' , sendIt)
                #print('output is: ' , output)
                #####go back and add each command's output to a different column. Right now its all in one cell. ####

            # Put gathered info into a row
            output_list = [host, output] 
            print('Adding this to report:' , output_list)
            output_q.put([output_list])
            
            # Cleanup SSH
            remote_shell.close()
            ssh.close()
            print('Closing SSH')

        except IndexError:
            pass
        except socket.error as e:
            ssh_error += ': Cannot connect to {} '.format(host)
            ssh_error += 'Socket error: '
            ssh_error += str(e)
            print('Cannot connect to {} '.format(host) + 'Socket error: ', e)
            ssh.close()
            return ssh_error
        except paramiko.AuthenticationException as e:
            ssh_error += ': Cannot connect to %s ' % (host) + 'Authentication failed: ' + str(e)
            print('Cannot connect to {} '.format(host) + 'Authentication failed: ', e)
            ssh.close()
            return ssh_error
        except socket.timeout as e:
            ssh_error += ': Cannot connect to %s ' % (host) + 'Socket timeout: ' + str(e)
            print('Cannot connect to {} '.format(host) + 'Socket timeout: ', str(e))
            ssh.close()
            return ssh_error
        except paramiko.SSHException as e:
            ssh_error += ': Cannot connect to %s ' % (host) + 'SSH Exception: ' +  str(e)
            print('Cannot connect to {} '.format(host) + 'SSH Exception: ', e)
            ssh.close()
            return ssh_error   

    finally:
        threadLimiter.release()


def CaptureScreen(remote_shell, deviceprompt):
    """ Summary: Capture last line and compare to original prompt. If they
        match then the command is done.

    Description:
        Takes the variable from deviceprompt and compares it to the last line
        of the screen capture. If the line doesn't match then its assumed
        that the previous command is still executing (it is assumed that the
        device pompt will return once the command is complete.. When the match
        is made the last screen is returned. This is used in cases such as
        an image upgrade on a network device where it takes several minutes to
        complete.

    Parameters:
        deviceprompt variable. Example: Switch1#
    """

    try: 
        # Capture the screen to see what has changed
        if remote_shell.recv_ready():
            outputnasty = remote_shell.recv(50000) # the output type is byte
            # Save the last line on the screen which will be used to check command's status
            try:
                lastline = outputnasty.decode('ascii').rsplit('\n' , 1)[1]
                if (lastline == None) or (lastline == ''):
                    lastline == 'PYTHON MESSAGE: No change detected.'
            except IndexError:
                lastline = 'PYTHON MESSAGE: No change detected.'
            except KeyboardInterrupt:
                print('\n Fine. Exiting')
                exit(0)
        else:
            outputnasty = 'PYTHON MESSAGE: No change detected.'
            lastline = 'PYTHON MESSAGE: Shell not ready.'

        # Now we are capturing the screen FOR REPORTING, assuming the command is complete (later)
        # Clear the first line
        try:
            output1 = outputnasty.decode('ascii').split('\n' , 1)[1]
            #print('output1 var: ' , output1)
            # Clear the last line
            output2 = output1.rsplit('\n' , 1)[0]
            #print('output2 var: ' , )
            deviceoutput = output2
            #print('deviceoutput var: ' , deviceoutput)
        except IndexError:
            deviceoutput = 'PYTHON MESSAGE: No change detected.'
        except AttributeError:
            pass
        except KeyboardInterrupt:
            print('\n Fine. Exiting')
            exit(0)
        
        # Compare last line to the device's prompt
        try:
            while (lastline.startswith(deviceprompt)):
                # Account for a question, notify the user, and accept the default value
                if ('[' in lastline) and (']' in lastline):
                    print('Question detected: ' , lastline)
                    print('Sending enter to accept the default value')
                    sendenter = '\n'
                    remote_shell.send(sendenter)
                    return CaptureScreen(remote_shell, deviceprompt)
                elif '-More-' in lastline:
                    print('-More- detected. Sending space to continue. Device: ' , deviceprompt)
                    print('')
                    sendspace = ' '
                    remote_shell.send(sendspace)
                    return CaptureScreen(remote_shell, deviceprompt)
                else:
                    try:
                        print('Command not done. Sleeping for 5 seconds. Device:', deviceprompt)
                        print('')
                        time.sleep(5)
                        return CaptureScreen(remote_shell, deviceprompt)
                    except KeyboardInterrupt:
                        print('\n Keyboard Interrupt. Exiting thread.')
                        deviceoutput = 'Keyboard Interrupt.'
                        return deviceoutput
                    
        except KeyboardInterrupt:
            print('\n Keyboard Interrupt. Exiting thread.')
            deviceoutput = 'Keyboard Interrupt.'
            return deviceoutput
        
        if deviceprompt == lastline:
            print('Command complete!')
            #print('deviceoutput: ' , deviceoutput)
            return deviceoutput

    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        exit(0)
        

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
    if pingstatus == True:
        ssh_exec_command(commands, host, user, pw, user_timeout, output_q)
    elif pingstatus == False:
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
            print('sleeping for 2 seconds...')
            time.sleep(2)
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
            exit(0)

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
            exit(0)
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
    #for devices in var:
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
        print('var: ' , CommandsourceVar)
        quit(0)
        CommandSource()

        


if __name__ == "__main__":

    # Clearing anything so we get a clean run
    counter = 0
    results = []
    my_dict = []
    output_q = Queue()
    user_timeout = 10000


    #signal.signal(signal.SIGINT, handler)
    
    
    # Defining date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    # Specifying the CSV export filename
    csvExport = 'results-{}.csv'.format(timestamp)
    writer = csv.writer(open(csvExport, 'w', newline=''))
    writer.writerow(['Host', 'Results'])

    print('\n' * 20) # May not want to clear screen, so just putting a bunch of blank lines
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
            time.sleep(1)
            IPs = []
            somecsvfile = tk.Tk()
            somecsvfile.withdraw()
            filename = filedialog.askopenfilename()
            print(filename)
            
            with open(filename , 'r') as infile:
                reader = csv.reader(infile)
                IPs = [rows[0] for rows in reader]

        elif IPSource == '3':
            IPs = []
            # Define solarwinds creds and connection settings
            npm_server = input('Enter IP for SolarWinds NPM: ')
            #npm_server = ''
            username = input('Enter username to connect with: ')
            #username = ''
            # Note: Running this script in IDLE this will give an error on getpass.
            #       This is an IDLE problem, not py problem
            password = getpass.getpass("Enter password: ")
            #password = ''

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

    # Get credentials for devices & setting some variables
    print('\n' * 2)
    print('Enter username to connect with.')
    user = input('(typically, the domain is not needed): ')
    print('')
    # Note: Running this script in IDLE this will give an error on getpass.
    #       This is an IDLE problem, not py problem
    pw = getpass.getpass("Enter password: ")
    print('\n' * 2)

    # Ask user how many threads they want to spawn
    threads = MaxThreads()
    threadLimiter = threading.BoundedSemaphore(threads)

    # Do the work, while limiting the number of threads
    for host in IPs:
        host = host.replace(' ','')
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

    # Get everything from the queue
    while not output_q.empty():
        my_dict = output_q.get()
        for datastuff in my_dict:
            writer.writerow(datastuff)
            
    print('\n' * 5)
    print('Results saved as:' , csvExport)
    print('\n' * 3)
