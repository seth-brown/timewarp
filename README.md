Time Warp
========

Time Machine Reservoir Sampler

Time Warp is a tool for modifying Time Machine's backup behavior using weighted reservoir sampling. Please see [this blog post](http://www.drbunsen.org/time_warp/) for an explain of the project prior to setup and use.

Requirements:
---------------

* OS X 10.7+

Setup Instructions
---------------

* Verify that the desired Time Machine Drive is mounted:

    _If you don't know how to do this, [see here](http://support.apple.com/kb/PH11173?viewlocale=en_US)._

* After cloning the repo, ensure Time Warp is in your path and executable:

  `$ chmod 755 timewarp.py`

* Modify the default config file (`safe-warp.json`) to point at the desired Time Machine volume. 

  Here's an example of what the configuration file should look like:
<pre>
{
    "mode": "safe",
    "volume": "/Volumes/Time Machine/Backups.backupdb/computer_name/",
    "threshold": 1024, 
    "log": "timewarp.log"
}
</pre>

* Run Time Warp in `safe-mode` using the modified config file from step 2:

  `$ ./timewarp.py safe-warp.json`

* Verify Time Warp is working by examining the log file, `timewarp.log`. This file contains the backup snapshot(s) that would have been deleted if the mode was set to `live`.

* Change the `mode` value to `"live"`.

  **DO NOT CHANGE THE THRESHOLD VALUE UNLESS YOU FULLY UNDERSTAND THE CONSEQUENCES**. Setting the mode to `live` and changing the `threshold` value to a large size could potentially delete every backup on a Time Machine hard drive.

* Move the provided plist file, `org.drbunsen.timewarp.plist` to the LaunchAgents folder and change the owner:

  `$ mv org.drbunsen.timewarp.plist /Library/LaunchAgents/`  
  `$ sudo chown root /Library/LaunchAgents/org.drbunsen.timewarp.plist`  
  `$ sudo launchctl load /Library/LaunchAgents/org.drbunsen.timewarp.plist`
