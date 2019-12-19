#!/usr/local/bin/python3
""" Summary: Looks at interface description using Netmiko and TextFSM.

Description:
    Prompts user for switch IP and what interface they want to get the
    decription for.

"""

__author__ = "Brandon Rumer"
__version__ = "1.0.1"
__email__ = "brumer@cisco.com"
__status__ = "Production"


""" Importing built-in modules """
import sys
import socket
import os
import argparse
import getpass
import re
import time


""" Import external modules """
from netmiko import Netmiko, file_transfer
from paramiko.ssh_exception import SSHException
import requests
import textfsm

       
def ssh_exec_command(checkinterface, host, user, pw, user_timeout):
    """ SSH to the device, sshsend checkinterface, and capture the output"""
    
    time.sleep(1)
    ssh_error = 'SSH Error'

    output = ''
    output_list = [] # one per device
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
            device_dict.update(Host = host)
            
            ssh = Netmiko(**device)
            
            print('')
            print('_____________________________________________________________')
            print('')
            print('Connection established to' , host)
            print('_____________________________________________________________')

            time.sleep(5)
            
            # Get the router/switches prompt. This will be used later to see if the checkinterface are done.
            deviceprompt = ssh.find_prompt() #NetMiko: find device prompt
            device_dict.update(Hostname = deviceprompt)

            ssh.send_command(
                'terminal length 0\n'
            )
            
            #print('COMPLETE: terminal length 0')

             # The string below doesn't work on slow or large stacks, so using send_command_timing instead
            ''' # The below doesn't work on 
            runningconfig = ssh.send_command(
               'sh run | sec interface\n' ,
                expect_string=r'#'
            )
            '''


            #######################################################
            ###### COMMAND WE WANT TO LOOK AT THE OUTPUT FOR ######
            #######################################################

            sendcommand = 'show run interface {} | i description'.format(checkinterface)
            #print('sendcommand: ' , sendcommand)
            showinterface = ssh.send_command(sendcommand , use_textfsm=True)
            
            #######################################################
            #######################################################
            
            #print('COMPLETE: show interface')
            #print('working on output...')
            #print(deviceprompt)
            interfacedescription = showinterface.split('description ' , 1)
            interfacedescription = interfacedescription[1]
            printlist = [host,checkinterface,interfacedescription]
            print('')
            print('On {} the interface {} has a description of "{}"'.format(host, checkinterface, interfacedescription))
            ssh.disconnect()
            exit(0)

            
        except IndexError:
            pass
        except SSHException:
            print('SSH error on' , host)

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

def main():

    try:
        parser = argparse.ArgumentParser(description='Process input device and interface.')
        parser.add_argument('-IP' , required=False, help='The IP to connect to')
        parser.add_argument('-interface', required=False, help='The interface to check. IE: gi1/0/1, gigabitethernet1/0/1')
        args = vars(parser.parse_args())
        print(args)
        if args['IP'] is None:
            print('')
            IP = input('Whats the IP of the device you want to check? ')
        else:
            IP = args['IP']
            
        if args['interface'] is None:
            print('')
            checkinterface = []
            print('What interface are you looking for?')
            checkinterface = input('ie: gi1/0/1, gigabitethernet1/0/1, etc...? ')
        else:
            checkinterface = args['interface']

        print('IP: {} & checkinterface: {}'.format(IP, checkinterface))

    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        exit(0)

    # Clearing anything so we get a clean run
    user_timeout = 10

                    
    # Get credentials for devices & setting some variables
    print('\n')
    print('Enter username to connect with.')
    user = input('(typically, the domain is not needed): ')
    print('')
    pw = getpass.getpass("Enter password: ")  #Running this script in IDLE this will give an error. This is an IDLE problem.
    #print('\n' * 2)
    

    host = IP

    # Do the work
    try:
        ssh_exec_command(checkinterface, host, user, pw, user_timeout)
    except KeyboardInterrupt:
        print('\n Fine. Exiting')
        exit(0)


if __name__ == "__main__":
    main()
