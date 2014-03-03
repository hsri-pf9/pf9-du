# Library for describing, implementing and managing pf9 apps #

## Interfaces ##

- App defines the behavior of an installed pf9 application
- RemoteApp derives from App and models a pf9 app that can be downloaded and installed.
- AppDb models a local application database (typically a package manager)
- AppCache models a download manager

## Algorithms ##

- process_apps() processes application configuration changes, and can cause
apps to be installed, deleted, upgraded, and reconfigured.

## Mock implementations ##

The names are self-explanatory

- MockInstalledApp
- MockRemoteApp
- MockAppDb
- MockAppCache
