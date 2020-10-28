#!/usr/local/bin/python3
""" Summary: Simple Query Application for Cisco Smartnet Total Care EOX API

Description:
    eoxquery is a very simple application that allows you to query either by 
    serial number or by product pid.

    Orignal authors: https://github.com/CiscoSE/eoxquery

"""

__author__ = "Branodn Rumer"
__version__ = "1.0.1"
__status__ = "Production"


""" Importing built-in modules """
import json
import sys
import csv

""" Import external modules """
import requests
import configparser


def get_csv():
    datafile = 'data.csv'
    devices = []
    print('Using' + datafile + ' as version input file.')
    print('')
    with open(datafile, 'r', newline='') as infile:
        for row in csv.reader(infile):
            # Remove any blank lines
            if any(entry.strip() for entry in row):
                devices.append(row[0])
    title = devices[0]
    if title.lower() == 'serial':
        searchtype = 'serial'
    if title.lower() == 'pid':
        searchtype = 'pid'
    del devices[0]
    return searchtype,devices


def get_access_token(client_id, client_secret):
    '''
    This function will get the access token from Cisco to be used in further queries

    :param client_id: the client id that was created on the apiconsole.cisco.com
    :param client_secret: the client secret that was created in apiconsole.cisco.com

    :return: access token to be used in other queries
    '''

    url = "https://cloudsso.cisco.com/as/token.oauth2?grant_type=client_credentials&client_id="+ \
        client_id + \
        "&client_secret="+ \
        client_secret

    headers = {
        'accept': "application/json",
        'content-type': "application/x-www-form-urlencoded",
        'cache-control': "no-cache"
    }

    response = requests.request("POST", url, headers=headers)

    if (response.status_code == 200):
        return response.json()['access_token']
    else:
        response.raise_for_status()


def get_eox_details(access_token,inputvalue,searchtype):
    ''' 
    This function will get the EOX record for a particular search

    :param access_token: Access Token retrieved from cisco to query the searchtypes
    :param inputvalue: The serial number of pid that is used to query
    :param searchtype: The type of search type to perform.   Either pid or serial
    :return: json format of the retrieved data
    '''

    if searchtype in ["pid"]:
        url = "https://api.cisco.com/supporttools/eox/rest/5/EOXByProductID/1/"+inputvalue+"?responseencoding=json"
    if searchtype in ["serial"]:
        url = "https://api.cisco.com/supporttools/eox/rest/5/EOXBySerialNumber/1/"+inputvalue+"?responseencoding=json"
    else:
        return

    headers = {
        'authorization': "Bearer " + access_token,
        'accept': "application/json",
    }

    response = requests.request("POST", url, headers=headers)

    if (response.status_code == 200):
        # Uncomment to debug
        #sys.stderr.write(response.text)
        #print (response.text)
        return json.loads(response.text)
    else:
        response.raise_for_status()
        return


def print_eox_details(data):
    '''
    :param data: json data of the retrieved data
    :return: none
    '''
    #print(data)

    EOLProductID=data['EOXRecord'][0]['EOLProductID']

    if EOLProductID == "":
        print ("No Records Found!")
    else:
        EOXInputValue=data['EOXRecord'][0]['EOXInputValue']

        ProductIDDescr=data['EOXRecord'][0]['ProductIDDescription']
        EOSDate = data['EOXRecord'][0]['EndOfSaleDate']['value']

        EOSWMDate=data['EOXRecord'][0]['EndOfSWMaintenanceReleases']['value']
        EOSSVulDate=data['EOXRecord'][0]['EndOfSecurityVulSupportDate']['value']
        EORoutineFailureDate=data['EOXRecord'][0]['EndOfRoutineFailureAnalysisDate']['value']
        EOSCRDate=data['EOXRecord'][0]['EndOfServiceContractRenewal']['value']
        LDOSDate=data['EOXRecord'][0]['LastDateOfSupport']['value']
        EOSvcAttachDate=data['EOXRecord'][0]['EndOfSvcAttachDate']['value']
        MigrationDetails=data['EOXRecord'][0]['EOXMigrationDetails']['MigrationProductId']

        print ("Search Value: " +EOXInputValue)
        print ("Product ID: "+EOLProductID)
        print ("Product Description: "+ProductIDDescr)
        print ("End of Sale Date ................. "+EOSDate)
        print ("End of Software Maint Date ....... "+EOSWMDate)
        print ("End of Security Vul Support Date . "+EOSSVulDate)
        print ("End of Routine Failure Date ...... "+EORoutineFailureDate)
        print ("End of Service Contract Date ..... "+EOSCRDate)
        print ("Last Date of Support Date ........ "+LDOSDate)
        print ("End of Service Attach Date ....... "+EOSvcAttachDate)
        print ("Migration PID: "+MigrationDetails)


def getClient():
    # Open up the configuration file and get all application defaults
    config = configparser.ConfigParser()
    config.read('package_config.ini')

    try:
        client_id = config.get("application","client_id")
        client_secret = config.get("application","client_secret")
    except configparser.NoOptionError:
        print("package_config.ini is not formatted approriately!")
        exit()
    except configparser.NoSectionError:
        print('package_config.ini error. Does the file exist in this directory?')
        exit()
    except:
        print("Unexpected Error")
        exit()

    access_token = get_access_token(client_id,client_secret)
    return access_token


def getdata(searchtype, device, access_token):
    try:
        if searchtype == None:
            data = input("Enter search string (ex: 'serial {serialnumber}' or 'pid {pid}' or 'quit'): ")
            if 'quit' in data.lower():
                sys.exit(0)
            searchtype,inputstring = data.split(" ",1)
            searchtype = searchtype.lower()
            if searchtype not in ['serial','pid']:
                print ("Unknown search type: "+searchtype+". Please try again")
                getdata(searchtype, device, access_token)
        else:
            inputstring = device

        print ("Performing "+searchtype+ " search for: '"+inputstring.upper()+"':")
        order_text = get_eox_details(access_token, str(inputstring.upper()),searchtype)
        print_eox_details(order_text)
        print('\n')

    except Exception:
        print('Unknown Error. Likely an input error. Quitting...')
        sys.exit(1)


def ManualOrCSV():
    print('\n')
    print('Would you like to use a:')
    print('  1. CSV for value input, or')
    print('  2. Manually enter pids/serials')
    SourceList = input('Press 1 or 2 : ')
    return SourceList


def main():
    device = None
    searchtype = None
    access_token = getClient()
    SourceList = ManualOrCSV()
    try:
        if SourceList.lower() == '1':
            searchtype,devices = get_csv()
            for device in devices:
                print(f'Checking: {device}')
                try:
                    getdata(searchtype, device, access_token)
                except KeyboardInterrupt:
                    print('Keyboard Interrupt. Exiting...\n')
                    sys.exit(0)
            sys.exit(0)

        if SourceList.lower() == '2':
            done = False
            getdata(searchtype, device, access_token)
            while not done:
                again = input('Run again?  (y/n)   ').lower()
                if again.lower() == 'y':
                    getdata(searchtype, device, access_token)
                else:
                    print('\n')
                    sys.exit(0)
        else:
            ManualOrCSV()
    except KeyboardInterrupt:
        print('Keyboard Interrupt. Exiting...')
        sys.quit(0)


if __name__ == "__main__":
    main()
    