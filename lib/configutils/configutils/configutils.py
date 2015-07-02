# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

"""
Contains utility methods that work with config files/data
"""

import ConfigParser
import errno
import json
import os


class MissingSectionError(Exception):
    """
    Exception thrown when the JSON object has keys which cannot be
    associated with a section (in ini format).
    """
    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "Missing section area for : %s" % self.section

class NestedSectionError(Exception):
    """
    Exception thrown when the JSON object has nesting more than 2 levels of
    dicts. This cannot be effectively represented in the ini format.
    """
    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "Nested sections found : %s" % self.section

def ini_to_json(iniConfig):
    """
    Converts an iniConfig object into JSON object.
    iniConfig is expected to be a ConfigParser object.
    To write out to a JSON file, use json.dump() on the output object.
    """
    # Ensure you are working with a ConfigParser object
    assert isinstance(iniConfig, ConfigParser.ConfigParser)
    out = {}

    # Need some extra handling here to deal with DEFAULT sections. The DEFAULT
    # section will get included in all other sections of the ConfigParser
    # object - which leads to these defaults being repeated in each section.
    # To deal with this, get the defaults (which is a dict), convert it to a set
    # of name, value tuples. Diff the actual section set with this defaults set.
    defaults = iniConfig.defaults()
    out["DEFAULT"] = defaults
    defaultslist = [(k,v) for (k,v) in defaults.iteritems()]
    defaultsset = set(defaultslist)

    for section in iniConfig.sections():
        sectionvals = {}
        tempset = set(iniConfig.items(section, raw=True))
        for key, value in (tempset - defaultsset):
            sectionvals[key] = value

        out[section] = sectionvals

    return out

def inifile_to_json(iniFile):
    """
    Read in a ini file and convert it to json config object.
    Raises exception if file is not found.
    """
    if not os.path.exists(iniFile):
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), iniFile)

    cfgparser = ConfigParser.ConfigParser()
    cfgparser.read(iniFile)

    return ini_to_json(cfgparser)

def json_to_ini(jsonConfig):
    """
    Converts an JSON object into ini config object.
    output is a ConfigParser object. To write the output to a file, use
    ConfigParser.write() method on the output.
    """
    out = ConfigParser.ConfigParser()
    for section, sectionval in jsonConfig.items():
        if not isinstance(sectionval, dict):
            # To satisfy the ini layout, the top level values in the JSON dict
            # should be dicts themselves. Else raise exception
            raise MissingSectionError(section)

        # By default, there is a DEFAULT section already in the config parser
        # object implying you cannot add such a section. Add sections only if it
        # is not DEFAULT.
        if section != 'DEFAULT':
            out.add_section(section)

        for key, val in sectionval.items():
            if isinstance(val, dict):
                # ini layouts cannot have nested sections. If we see multiple
                # levels of dicts (i.e. other than first level), raise exception
                raise NestedSectionError(key)

            out.set(section, key, str(val))

    return out

def jsonfile_to_ini(jsonFile):
    """
    Read in a file and convert it to ini config object.
    Raises exception if file is not found or if the file is not of JSON format.
    """
    if not os.path.exists(jsonFile):
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), jsonFile)

    cfg = {}
    with open(jsonFile, 'r') as f:
        cfg = json.load(f)

    return json_to_ini(cfg)


def is_dict_subset(dict1, dict2):
    """
    Tests if a JSON compatible dictionary is fully included in another. The subset
    check is done from the top level keys, i.e. all the top level keys of dict1
    should be present as the top level keys of dict2 for a potential subset match.
    Currently, the values for the dictionary keys can be str, bool, int, float
    or another dict.

    :param dict dict1: The first dictionary
    :param dict dict2: The second dictionary
    :return: true if dict1 is subset of dict2
    :rtype: bool
    """
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return False

    for key, val1 in dict1.items():
        # key doesn't exist in dict2
        if key not in dict2:
            return False

        type1 = type(val1)
        if type1 not in (str, unicode, bool, int, float, dict):
            # Currently we support only these datatypes as values in the dict
            return False
        val2 = dict2[key]
        if issubclass(type1, dict):
            # If there is a nested dict, recurse the call.
            if not is_dict_subset(val1, val2):
                return False
        elif val1 != val2:
            return False

    return True
