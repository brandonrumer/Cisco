# RecommendedVersion
Simple Query Application for Cisco Recommended Software Version API

## Requirements
This application requires access to the "Software Suggestion" API provided at [https://apiconsole.cisco.com/](https://apiconsole.cisco.com/). 

Details of the API is documented at the following link: [https://developer.cisco.com/docs/support-apis/#!software-suggestion/get-suggested-releases-and-images-by-product-ids](https://developer.cisco.com/docs/support-apis/#!software-suggestion/get-suggested-releases-and-images-by-product-ids)

You will need to register for an account. This will allow you to request access to the API which allows you to query for Cisco Access. In addition when you register, you can generate client credentials that will then be used within the package_config.ini file. A sample file is provided.

## Usage
recomver is a very simple application that allows you to query Cisco.com by product pid.

An example is shown below. 

```
Performing PID search for:         WS-C3750X-24P-S
Product ID........................ WS-C3750X-24P-S
Product Description............... Catalyst 3750X-24P-S Switch
Software Type..................... IOS Software
Software Version.................. 15.2(4)E10
Software Release Date............. 07-Apr-2020
Software Release Cycle............ MD
Image filename.................... c3750e-universalk9-mz.152-4.E10.bin
Image size........................ 25549824
Required DRAM on device........... 256 MB
Required Flash on device.......... 64 MB
```

## Extended Usage
The script prompts for a CSV to be used, or manual interaction is possible. If a CSV is used, there should be a single column of PIDs with no header. 

## Notes
The device will return a 'not found' if the device cannot be found in Cisco's database. This likely means there is an error in the script or the product PID is incorrect.
