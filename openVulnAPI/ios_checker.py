#!/usr/bin/env python3
"""
Summary:
     Programmatically keep up with security vulnerability information
     via REST APIs via Cisco DevNet.
Description:
    Based on Cisco PSIRT openVuln API sample code.

    Replace openvuln_clientid and openvuln_secret.
        Client ID and Secret can be obtained on the openVuln website,
        https://developer.cisco.com/site/PSIRT/
        https://apiconsole.cisco.com/
Usage:
    ios_checker.py --file [filename]
        Where [filename] is a single column list of IOS and IOS-XE versions to check.

Requirements:
    oauth2, argparse
"""


"""  Importing built-in modules """
import json
import urllib.request
import sys
import datetime
import time
import csv

"""  Importing third-party modules """
import oauth2 as oauth
import argparse


__author__ = "Sean Sutherland, Brandon Rumer"
__version__ = "1.3"
__email__ = "sesuther@cisco.com, brumer@cisco.com"
__status__ = "Production"


def process_args():
    parser = argparse.ArgumentParser(description='Checks Cisco for pSIRTs on specific IOS/IOS-XE code.', \
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        '--file',
        action='store',
        metavar='file',
        required=True,
        help='Input CSV file of IOS Versions:'
        )
    parser.add_argument(
        '--export',
        action='store_true',
        required=False,
        help='Save results as a CSV.'
        )
    return parser.parse_args()


def YorN():
    #  Ask user Y or N
    try:
        if (YesOrNo == 'n') or (YesOrNo == 'y'):
            return YesOrNo
    except UnboundLocalError:
        pass
    print('')
    YesOrNo = input('Do you want to export results to a CSV? y/n  ').lower()
    if (YesOrNo == 'n') or (YesOrNo == 'y'):
        return YesOrNo
    else:
        print('Syntax Error')
        YesOrNo = YorN()


def main():
    args = process_args()

    #################################################################################################
    #  Within single quotes, define the clientid and secret that was given from developer.cisco.com #
    openvuln_clientid = ''
    openvuln_secret = ''
    #################################################################################################

    #  Define date & time
    today_str = str(datetime.date.today())
    timestamp = str(today_str + '-' + (time.strftime('%H%M%S')))

    try:
        consumer = oauth.Consumer(key=openvuln_clientid, secret=openvuln_secret)
        request_token_url = "https://cloudsso.cisco.com/as/token.oauth2?grant_type=client_credentials&client_id=" + openvuln_clientid + "&client_secret=" + openvuln_secret
        client = oauth.Client(consumer)
        resp, content = client.request(request_token_url, "POST")
    except Exception:
        sys.stderr.write("Unable to retrieve access token.")
        sys.exit(1)

    print('_____________________________________________________________')
    print('')
    print('                  IOS Checker CLI Interface')
    print('_____________________________________________________________')

    YesOrNo = YorN()
    try:
        if YesOrNo == 'y':
            csvExport = 'pSIRT_results-{}.csv'.format(timestamp)
            writer = csv.writer(open(csvExport, 'w', newline=''))
            writer.writerow(['Version', 'pSIRT_ID', 'Advisory_Title', 'Severity'])
    except Exception:
        #Catches error on user input, and just outputs to screen
        YesOrNo == 'n'

    versionfile = str(sys.argv[2])
    print('Using ' + versionfile + ' as version input file.')
    print('')
    with open(versionfile, 'r') as infile:
        reader = csv.reader(infile)

        for version in reader:
            if (version[0].startswith('12')) or (version[0].startswith('15')):
                type = "ios"
            else:
                type = "iosxe"

            j = json.loads(content.decode('utf-8'))

            print('Checking version ', version[0])

            try:
                req = urllib.request.Request('https://api.cisco.com/security/advisories/' + type + '?version=' + version[0])
                req.add_header('Accept', 'application/json')
                req.add_header('Authorization', 'Bearer ' + j['access_token'])

                try:
                    resp = urllib.request.urlopen(req)
                    adv = resp.read()
                    advdata = json.loads(adv.decode('utf-8'))
                    #print('advdata:',advdata)
                    if YesOrNo =='y':
                        print('Saving to CSV:')
                    for advisory in advdata['advisories']:
                        if YesOrNo == 'n':
                            print(version[0], ',', advisory['advisoryId'], ',', advisory['advisoryTitle'], ',', advisory['sir'])
                            print("")
                        elif YesOrNo == 'y':
                            writer.writerow([version[0], advisory['advisoryId'], advisory['advisoryTitle'], advisory['sir']])
                            print(version[0], ',', advisory['advisoryId'], ',', advisory['advisoryTitle'], ',', advisory['sir'])
                            print("")
                        else:
                            continue
                except KeyboardInterrupt:
                    print('\n User Interrupt. Exiting.')
                    sys.exit(0)

            except urllib.error.HTTPError as err:
                print(version[0] + ",Error")


if __name__ == "__main__":
    main()
