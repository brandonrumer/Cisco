#!/usr/local/bin/python3
""" Summary: Connects to multiple Cisco Catalyst switches and upgrades them.

Description:
    Imports a CSV of IPs and upgrade files. Then this script
    connects to each device and stages the software. The output
    is captured and exported to a CSV.

    Multithreading is used so that multiple devices can be upgraded at
    the same time. The user is asked how many threads are to be used so
    the python-hosted computer or network isn't saturated.
"""

__author__ = "Brandon Rumer"
__version__ = "1.0.1"
__email__ = "brumer@cisco.com"
__status__ = "Development"


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

""" Import external modules """
import paramiko
import requests

     
def ssh_exec_command(host, binary, ftpserver, user, pw, user_timeout, output_q):
    """ SSH to the device, send commands, and capture the output """
    output = ''
    output_list = []
    ssh_error = 'SSH Error'

    # Building install command
    slash = '/'
    ftpprefix = 'ftp://'
    ftpfile = ftpprefix + ftpserver + slash + binary

    packageinstall = 'request platform software package install switch all file ftp://{} on-reboot new auto-copy'.format(ftpfile)
    verifycommand = 'show version provisioned | i version'
    commands = ['request platform software package clean' , packageinstall, verifycommand]

    print('')
    print('On' , host , ', I am going to run:')
    for n in commands:
        print(n)
    print('')
        
    CountOfCommands = len(commands)
    # print('commands: ' , commands)
    
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
            time.sleep(2)

            # Clear Output (banner)
            if remote_shell.recv_ready():
                output = remote_shell.recv(10000)
                # Get the router/switches prompt. This will be used later to see if the commands are done.
                deviceprompt = output.decode('ascii').rsplit('\n' , 1)[1]
                # print('device prompt var: ' , deviceprompt)


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
                print('Done with command')
                print('output is: ' , output)
                #####go back and add each command's output to a different column. Right now its all in one cell. ####


            # Put gathered info into a row
            output_list = [host, output] 
            print('Adding this to report:' , output_list)
            output_q.put([output_list])
            
            # Cleanup SSH
            remote_shell.close()
            ssh.close()
            print('Closing SSH')

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
        while (deviceprompt != lastline):
            # Account for a question, notify the user, and accept the default value
            if ('[y/n]' in lastline):
                print('y or n question detected: ' , lastline)
                print('Sending y')
                sendenter = 'y\n'
                remote_shell.send(sendenter)
                time.sleep(2)
                return CaptureScreen(remote_shell, deviceprompt)
            elif ('[' in lastline) and (']' in lastline):
                print('Open-ended question detected: ' , lastline)
                print('Sending enter to accept the default value')
                sendenter = '\n'
                remote_shell.send(sendenter)
                time.sleep(2)
                return CaptureScreen(remote_shell, deviceprompt)
            else:
                print('Command not done. Sleeping for 10 seconds.')
                time.sleep(10)
                return CaptureScreen(remote_shell, deviceprompt)
        if deviceprompt == lastline:
            print('Command complete!')
            print('Last screen captured: ' , deviceoutput)
            return deviceoutput

    #except IndexError:
        #pass
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


def WorkIt(host, binary, ftpserver, user, pw, user_timeout, output_q):
    """ Placeholder function, primarily needed for multithreading  """
    pingstatus = check_pingv2(host)
    if pingstatus == True:
        ssh_exec_command(host, binary, ftpserver, user, pw, user_timeout, output_q)
    elif pingstatus == False:
        threadLimiter.release()


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
    
    threads = input('Max concurrent devices do you want to connect to (default 5): ')
    if threads == '':
        threads = int('5')
        return threads
    else:
        try:
            number = int(threads)
            return number
        except ValueError:
            print('Only input numeric numbers!')
            print('')
            Maxthreads()



if __name__ == "__main__":

    # Clearing anything so we get a clean run
    counter = 0
    results = []
    my_dict = []
    output_q = Queue()
    user_timeout = 10000

    # Defining date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    # Specifying the CSV export filename
    csvExport = 'results-{}.csv'.format(timestamp)
    writer = csv.writer(open(csvExport, 'w', newline=''))
    writer.writerow(['Host', 'Results'])
   

    print('\n' * 20)
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
    print('This script will update Catalyst 3000 and 9000 switches. It supports multithreading so multiple')
    print('switches can be upgraded at the same time. Take care not to overload the server hosting the binary')
    print('files. This script should NOT be used on 3.x code, and should only be used for 16.x code.')
    print('\n')
    print('Please note: if "[yes or no]" is detected in the same line, this script will choose yes. If the')
    print('script asks for additional input, and "[" and "]" are detected in the same line (without')
    print('yes or no) , this script will assume that the device is asking for input. The default value will be')
    print('chosen. If this is not acceptable then this script may not be suitable for the command.')
    print('\n' * 1)
    print('The CSV file should have two columns with column names ip & binary. The first column should have ')
    print('the switch IP Address, and the second the binary file that you want to upgrade to. The binary file ')
    print('should be at the root directory of the FTP server.')
    print('\n')
    print('CSV example: ip,binary')
    print('             10.10.10.1,cat3k_caa-universalk9.16.06.06.SPA.bin')
    print('             10.10.10.2,cat3k_caa-universalk9.16.06.06.SPA.bin')
    print('             10.10.10.3,cat3k_caa-universalk9.16.03.08.SPA.bin')
    print('\n' * 1)
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    print('///////////////////////////////////////////////////////////////////////////////////////////////////')
    time.sleep(3)

    
    IPs = []
    somecsvfile = tk.Tk()
    somecsvfile.withdraw()

    filename = filedialog.askopenfilename()
    print('')
    print('Using this CSV file: ' , filename)
    print('')


    # Get credentials for devices & setting some variables
    ftpserver = input('FTP Server IP Address: ')
    print('')
    print('Enter username to connect to the switch with.')
    user = input('(typically, the domain is not needed): ')
    print('')
    # Note: Running this script in IDLE this will give an error on getpass.
    #       This is an IDLE problem, not py problem
    pw = getpass.getpass("Enter password: ")
    print('')
    

    # Ask user how many threads they want to spawn
    threads = MaxThreads()
    threadLimiter = threading.BoundedSemaphore(threads)


    # Do the work, while limiting the number of threads
    with open(filename , 'r') as infile:
        reader = csv.reader(infile, delimiter=',')

        for row in reader:
            try:
                host = row[0]
                binary = row[1]
                threadLimiter.acquire()
                my_thread = threading.Thread(target=WorkIt, args=(host, binary, ftpserver, user, pw, user_timeout, output_q))
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
