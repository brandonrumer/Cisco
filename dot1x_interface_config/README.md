# About
Checks if interfaces have port-security on them.

Could be useful if port-security is required. Could also be useful if dot1x is being used and port-security should not be used.
 
If port-security is found, the whole interface's config is reported in the JSON report that is generated.

If no interface has port-security on the device, then the device is not included in the JSON report.

## Prerequisites

Python3, NetMiko, TextFSM, CiscoConfParse

### Note

Use these at your own risk. I am not responsible for config losses or damage that may occur with the use of these scripts.

## License

This project is licensed under the GNU3 License - see the LICENSE.md file for details
