#!/usr/bin/env python3
""" Summary: Simple Query Application for Cisco Smartnet Total Care EOX API

Description:
    eoxquery is a very simple application that allows you to query either by
    serial number or by product pid.

    The script prompts for a CSV to be used, or manual interaction is possible.
    If a CSV is used, there should be a single column of serial numbers or PIDs,
    with the header (first line) containing either 'serial' or 'pid'.

    Orignal authors: https://github.com/CiscoSE/eoxquery

"""

__author__ = "Brandon Rumer"
__version__ = "1.0.2"
__email__ = "brumer@cisco.com"
__status__ = "Production"


""" Importing built-in modules"""
import json
import sys
import csv
import datetime
import time

""" Import external modules """
import requests
import configparser


def get_csv(datafile):

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
    return searchtype, devices


def get_access_token(client_id, client_secret):
    '''
    This function will get the access token from Cisco to be used in further queries

    :param client_id: the client id that was created on the apiconsole.cisco.com
    :param client_secret: the client secret that was created in apiconsole.cisco.com

    :return: access token to be used in other queries
    '''

    url = "https://cloudsso.cisco.com/as/token.oauth2?grant_type=client_credentials&client_id=" + \
        client_id + \
        "&client_secret=" + \
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


def get_eox_details(access_token, inputvalue, searchtype):
    '''
    This function will get the EOX record for a particular search

    :param access_token: Access Token retrieved from cisco to query the searchtypes
    :param inputvalue: The serial number of pid that is used to query
    :param searchtype: The type of search type to perform.   Either pid or serial
    :return: json format of the retrieved data
    '''
    if searchtype in ["pid"]:
        url = "https://api.cisco.com/supporttools/eox/rest/5/EOXByProductID/1/" + inputvalue + "?responseencoding=json"
    elif searchtype in ["serial"]:
        url = "https://api.cisco.com/supporttools/eox/rest/5/EOXBySerialNumber/1/" + inputvalue + "?responseencoding=json"
    else:
        return

    headers = {
        'authorization': "Bearer " + access_token,
        'accept': "application/json",
    }

    response = requests.request("POST", url, headers=headers)

    if (response.status_code == 200):
        # Uncomment to debug
        # sys.stderr.write(response.text)
        # print (response.text)
        return json.loads(response.text)
    else:
        response.raise_for_status()
        return


def print_eox_details(data, export):
    '''
    This function will parse the desired value from a particular search

    :param data: the json data returned from the get_eox_detailsget_eox_details function
    :param export: the user's y/n input for exporting all the results to a csv
    :return: list of desired values from the device
    '''
    try:
        EOLProductID = data['EOXRecord'][0]['EOLProductID']
        if EOLProductID == "":
            print("No Records Found!")
            if export == 'y':
                devicedata = [data['EOXRecord'][0]['EOXInputValue'], 'Not Found', 'Not Found', 'Not Found',
                'Not Found', 'Not Found', 'Not Found', 'Not Found', 'Not Found', 'Not Found', 'Not Found']
                return devicedata
            else:
                return None
        else:
            EOXInputValue = data['EOXRecord'][0]['EOXInputValue']

            ProductIDDescr = data['EOXRecord'][0]['ProductIDDescription']
            EOSDate = data['EOXRecord'][0]['EndOfSaleDate']['value']

            EOSWMDate = data['EOXRecord'][0]['EndOfSWMaintenanceReleases']['value']
            EOSSVulDate = data['EOXRecord'][0]['EndOfSecurityVulSupportDate']['value']
            EORoutineFailureDate = data['EOXRecord'][0]['EndOfRoutineFailureAnalysisDate']['value']
            EOSCRDate = data['EOXRecord'][0]['EndOfServiceContractRenewal']['value']
            LDOSDate = data['EOXRecord'][0]['LastDateOfSupport']['value']
            EOSvcAttachDate = data['EOXRecord'][0]['EndOfSvcAttachDate']['value']
            MigrationDetails = data['EOXRecord'][0]['EOXMigrationDetails']['MigrationProductId']
            print("Search Value: " + EOXInputValue)
            print("Product ID: " + EOLProductID)
            print("Product Description: " + ProductIDDescr)
            print("End of Sale Date ................. " + EOSDate)
            print("End of Software Maint Date ....... " + EOSWMDate)
            print("End of Security Vul Support Date . " + EOSSVulDate)
            print("End of Routine Failure Date ...... " + EORoutineFailureDate)
            print("End of Service Contract Date ..... " + EOSCRDate)
            print("Last Date of Support Date ........ " + LDOSDate)
            print("End of Service Attach Date ....... " + EOSvcAttachDate)
            print("Migration PID: " + MigrationDetails)
            print('\n')
            if export == 'y':
                devicedata = [EOXInputValue, EOLProductID, ProductIDDescr, EOSDate,
                EOSWMDate, EOSSVulDate, EORoutineFailureDate, EOSCRDate, LDOSDate,
                EOSvcAttachDate, MigrationDetails]
                return devicedata
            else:
                return None
    except Exception:
        return None


def getClient():
    # Open up the configuration file and get all application defaults
    config = configparser.ConfigParser()
    config.read('package_config.ini')

    try:
        client_id = config.get("application", "client_id")
        client_secret = config.get("application", "client_secret")
    except configparser.NoOptionError:
        print("package_config.ini is not formatted approriately!")
        sys.exit(1)
    except configparser.NoSectionError:
        print('package_config.ini error. Does the file exist in this directory?')
        sys.exit(1)
    except:
        print("Unexpected Error")
        sys.exit(1)

    access_token = get_access_token(client_id, client_secret)
    return access_token


def getdata(searchtype, device, access_token):
    try:
        if searchtype is None:
            data = input("Enter search string (ex: 'serial {serialnumber}' or 'pid {pid}' or 'quit'): ")
            if 'quit' in data.lower():
                sys.exit(0)
            searchtype, inputstring = data.split(" ", 1)
            searchtype = searchtype.lower()
            if searchtype not in ['serial', 'pid']:
                print("Unknown search type: " + searchtype + ". Please try again")
                getdata(searchtype, device, access_token)
        else:
            inputstring = device

        print("Performing " + searchtype + " search for: '" + inputstring.upper() + "':")
        order_text = get_eox_details(access_token, str(inputstring.upper()), searchtype)
        # print_eox_details(order_text)
        return order_text

    except Exception:
        print('Unknown Error. Sleeping for 10 seconds. Hoping things clear up.')
        time.sleep(10)
        return None


def ManualOrCSV():
    print('\n')
    print('Would you like to use a:')
    print('  1. CSV for value input, or')
    print('  2. Manually enter pids/serials')
    SourceList = input('Press 1 or 2 : ')
    return SourceList


def main():
    ########################################################################
    # This is the input file used if a list of serials/pids are to be used #
    ########################################################################
    datafile = 'data.csv'
    ########################################################################
    ########################################################################

    device = None
    searchtype = None
    devicetable = []
    access_token = getClient()
    SourceList = ManualOrCSV()

    # Defining date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    try:
        # Use a CSV for the source. This also allows the results to be exported to a CSV.
        if SourceList.lower() == '1':
            export = input('Would you like to save the results in a CSV? (y/n) ')
            if export == 'y':
                csvExport = 'outfile-{}.csv'.format(timestamp)
                # Specifying the CSV export filename
                writer = csv.writer(open(csvExport, 'w', newline=''))
                writer.writerow(['Device', 'Product ID', 'Description', 'End of Sale',
                'End of Software Maint', 'End of Security Vul Support', 'End of Routine Failure',
                'End of Service Contract', 'Last Date of Support', 'End of Service Attach',
                'Migratin PID'])
            else:
                export == 'n'

            searchtype, devices = get_csv(datafile)
            for device in devices:
                try:
                    order_text = getdata(searchtype, device, access_token)
                except KeyboardInterrupt:
                    print('Keyboard Interrupt. Exiting...\n')
                    break
                finally:
                    devicedata = print_eox_details(order_text, export)
                    devicetable.append(devicedata)

            if export == 'y':
                with open(csvExport, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Device', 'Product ID', 'Description', 'End of Sale',
                    'End of Software Maint', 'End of Security Vul Support', 'End of Routine Failure',
                    'End of Service Contract', 'Last Date of Support', 'End of Service Attach',
                    'Migratin PID'])
                    for item in devicetable:
                        if item is None:
                            # Accounts for a 'No records found'
                            pass
                        else:
                            writer.writerow(item)
                print(f'CSV saved at: {csvExport}')
            sys.exit(0)

        # Manual entry of serials/pids
        if SourceList.lower() == '2':
            export = 'n'
            done = False
            order_text = getdata(searchtype, device, access_token)
            print_eox_details(order_text, export)
            while not done:
                again = input('Run again?  (y/n)   ').lower()
                if again.lower() == 'y':
                    order_text = getdata(searchtype, device, access_token)
                    print_eox_details(order_text, export)
                else:
                    print('\n')
                    sys.exit(0)
        else:
            ManualOrCSV()

    except KeyboardInterrupt:
        print('Keyboard Interrupt. Exiting...')
        sys.exit(0)


if __name__ == "__main__":
    main()
