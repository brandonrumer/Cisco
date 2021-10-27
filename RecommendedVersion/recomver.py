#!/usr/bin/env python3
""" Summary: Simple Query Application for Cisco Recommended Software Version

Description:
    RecomVer is a very simple application that allows you to query by product pid.

    The script prompts for a CSV to be used, or manual interaction is possible.
    If a CSV is used, there should be a single column of PIDs.
"""

__author__ = "Brandon Rumer"
__version__ = "1.0.0"
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
    return devices


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


def get_softver_details(access_token, device):
    '''
    This function will get the Recommended Software record for a particular search
    :param access_token: Access Token retrieved from cisco to query
    :return: json format of the retrieved data
    '''

    url = f"https://api.cisco.com/software/suggestion/v2/suggestions/software/productIds/{device}?pageIndex=1"

    headers = {
        'authorization': "Bearer " + access_token,
        'accept': "application/json",
    }

    response = requests.request("GET", url, headers=headers)

    if (response.status_code == 200):
        # Uncomment to debug
        # sys.stderr.write(response.text)
        # print (response.text)
        return json.loads(response.text)
    if (response.status_code == 404):
        # Uncomment to debug
        # sys.stderr.write(response.text)
        # print (response.text)
        response.text = ''
        return json.loads(response.text)
    else:
        response.raise_for_status()
        return


def print_soft_details(data, export, device):
    '''
    This function will parse the desired value from a particular search
    :param data: the json data returned from the get_softver_detailsget_softver_details function
    :param export: the user's y/n input for exporting all the results to a csv
    :return: list of desired values from the device
    '''
    try:
        ProductID = data['productList'][0]['product']
        if ProductID == "":
            print("No Records Found!")
            if export == 'y':
                devicedata = [device, 'Not Found', 'Not Found', 'Not Found',
                              'Not Found', 'Not Found', 'Not Found', 'Not Found',
                              'Not Found', 'Not Found']

                return devicedata
            else:
                return None
        else:
            # productList = data['productList']
            basePID = data['productList'][0]['product']['basePID']
            productName = data['productList'][0]['product']['productName']
            softwareType = data['productList'][0]['product']['softwareType']
            for item in data['productList'][0]['suggestions']:
                softversion = item['releaseFormat2']
                releaseDate = item['releaseDate']
                releaseLifeCycle = item['releaseLifeCycle']
                for vercode in item['images']:
                    if (vercode['featureSet'].upper().endswith('UNIVERSAL')) or (vercode['featureSet'].upper() == 'LAN BASE'):
                        imageName = vercode['imageName']
                        imageSize = vercode['imageSize']
                        requiredDRAM = vercode['requiredDRAM']
                        requiredFlash = vercode['requiredFlash']
                    else:
                        imageName = "Multiple Images"
                        imageSize = "Multiple Images"
                        requiredDRAM = "Multiple Images"
                        requiredFlash = "Multiple Images"

            print("Product ID........................ " + basePID)
            print("Product Description............... " + productName)
            print("Software Type..................... " + softwareType)
            print("Software Version.................. " + softversion)
            print("Software Release Date............. " + releaseDate)
            print("Software Release Cycle............ " + releaseLifeCycle)
            print("Image filename.................... " + imageName)
            print("Image size........................ " + imageSize)
            print("Required DRAM on device........... " + requiredDRAM)
            print("Required Flash on device.......... " + requiredFlash)
            print('\n')
            if export == 'y':
                devicedata = [basePID, productName, softwareType, softversion,
                              releaseDate, releaseLifeCycle, imageName, imageSize,
                              requiredDRAM, requiredFlash]
                return devicedata
            else:
                return None
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(e)


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


def getdata(device, access_token):
    try:
        print(f"Performing PID search for:         {device}")
        order_text = get_softver_details(access_token, device)
        return order_text

    except Exception as e:
        print(e)
        print('\n')
        print('Error. Sleeping for 10 seconds. Hoping things clear up.')
        time.sleep(10)
        return None


def ManualOrCSV():
    print('\n')
    print('Would you like to use a:')
    print('  1. CSV for value input, or')
    print('  2. Manually enter pids')
    SourceList = input('Press 1 or 2 : ')
    return SourceList


def main():
    ########################################################################
    #     This is the input file used if a list of pids are to be used     #
    ########################################################################
    datafile = 'data.csv'
    ########################################################################
    ########################################################################

    device = None
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
                                 'End of Software Maint', 'End of Security Vul Support',
                                 'End of Routine Failure', 'End of Service Contract',
                                 'Last Date of Support', 'End of Service Attach',
                                 'Migratin PID'])
            else:
                export == 'n'

            devices = get_csv(datafile)
            for device in devices:
                try:
                    order_text = getdata(device, access_token)
                    # print(json.dumps(order_text))
                except KeyboardInterrupt:
                    print('Keyboard Interrupt. Exiting...\n')
                    break
                finally:
                    devicedata = print_soft_details(order_text, export, device)
                    devicetable.append(devicedata)

            if export == 'y':
                with open(csvExport, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Product ID', 'Description', 'Software Type',
                                     'Recommended Software Version', 'Software Release Date',
                                     'Software Release Cycle', 'Universal Image Filename',
                                     'Image Size', 'Required DRAM Size', 'Required Flash Size'])
                    for item in devicetable:
                        if item is None:
                            # Accounts for a 'No records found'
                            pass
                        else:
                            writer.writerow(item)
                print(f'CSV saved at: {csvExport}')
            sys.exit(0)

        # Manual entry of pids
        if SourceList.lower() == '2':
            export = 'n'
            done = False
            device = input('Type PID to look for: ').upper()
            order_text = getdata(device, access_token)
            print_soft_details(order_text, export)
            while not done:
                again = input('Run again?  (y/n)   ').lower()
                if again.lower() == 'y':
                    device = input('Type PID to look for: ').upper()
                    order_text = getdata(device, access_token)
                    print_soft_details(order_text, export)
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
