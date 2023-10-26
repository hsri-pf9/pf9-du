# PF9 Config Utilities #

This module provides a utility methods that work with config files/data

## Methods ##

- ini_to_json(iniConfig): Converts an iniConfig object into JSON object. iniConfig is expected to be a ConfigParser object. To write out to a JSON file, use json.dump() on the output object.

- inifile_to_json(iniFile): Read in a ini file and convert it to json config object. Raises OSError exception if file is not found.

- json_to_ini(jsonConfig): Converts an JSON object into ini config object. Output is a ConfigParser object. To write the output to a file, use ConfigParser.write() method on the output. Throws MissingSectionError or NestedSectionError.

- jsonfile_to_ini(jsonFile): Read in a file and convert it to ini config object. Raises OSError exception if file is not found or ValueError exception if the file is not of JSON format.

- is_dict_subset(dict1, dict2): Tests if a JSON compatible dictionary is fully included in another. The subset check is done from the top level keys, i.e. all the top level keys of dict1 should be present as the top level keys of dict2 for a potential subset match. Currently, the values for the dictionary keys can be str, bool, int, float or another dict.

## Exceptions ##

- MissingSectionError: Exception thrown when the JSON object has keys which cannot be associated with a section (in ini format).

- NestedSectionError: Exception thrown when the JSON object has nesting more than 2 levels of dicts. This cannot be effectively represented in the ini format.
