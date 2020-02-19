# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

"""
Contains utility methods that work with config files/data
"""

import copy
import json
import os
import re
import shutil
import tempfile
import six
from six.moves.configparser import ConfigParser
from six import iteritems
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
    assert isinstance(iniConfig, ConfigParser)
    out = {}

    # Need some extra handling here to deal with DEFAULT sections. The DEFAULT
    # section will get included in all other sections of the ConfigParser
    # object - which leads to these defaults being repeated in each section.
    # To deal with this, get the defaults (which is a dict), convert it to a set
    # of name, value tuples. Diff the actual section set with this defaults set.
    defaults = iniConfig.defaults()
    out["DEFAULT"] = defaults
    defaultslist = [(k,v) for (k,v) in iteritems(defaults)]
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

    cfgparser = ConfigParser()
    cfgparser.read(iniFile)

    return ini_to_json(cfgparser)

def json_to_ini(jsonConfig):
    """
    Converts an JSON object into ini config object.
    output is a ConfigParser object. To write the output to a file, use
    ConfigParser.write() method on the output.
    """
    out = ConfigParser()
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

            try:
                out.set(section, key, str(val))
            except ValueError:
                # ValueError produces val, that needs to be converted to raw format
                # so as not to invalid interpolation error.
                val = val.replace("%", "%%")
                out.set(section, key, val)

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
        if six.PY2:
            if type1 not in (str, unicode, bool, int, float, dict):
                # Currently we support only these datatypes as values in the dict
                return False
        else:
            if type1 not in (str, bool, int, float, dict):
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


SECPAT = re.compile(r'\s*\[\s*(\S+)\s*]')
KEYPAT = re.compile(r'\s*(\S+)\s*=\s*(\S[^\r\n]*)')


def extract_params(params, inifile, cfg= None):
    """
    extract dictionary with keys specified in params from an inifile
    """
    if cfg is None:
        cfg = {}
    with open(inifile, 'r') as f:
        section = None
        for line in f.readlines():
            secmatch = SECPAT.match(line)
            if secmatch:
                section = secmatch.group(1)
            else:
                keymatch = KEYPAT.match(line)
                if keymatch:
                    key, val = keymatch.groups()
                    if section in params and key in params[section]:
                        if section in cfg:
                            cfg[section][key] = val
                        else:
                            cfg[section] = {key: val}
    return cfg


def merge_params(params, inifile):
    """
    Merge a two-level json dictionary into an ini file.
    :param params: dictionary with keys representing sections in the
                   ini file. Values are dictionaries representing
                   parameter values within the section.
    :param inifile: File to modify.
    """
    # create the file if it's not already there
    if not os.path.isfile(inifile):
        open(inifile, 'w').close()

    # Use a copy of the params to keep track of state, removing keys/sections
    # as we find and modify them in the file. Leftover keys are added at the
    # end of a section. Leftover sections are added at the end of the file.
    currsect = None
    unset = copy.deepcopy(params)
    with tempfile.NamedTemporaryFile(mode='w',prefix=os.path.basename(inifile),
                                     delete=False) as ofile:
        with open(inifile, 'r') as ifile:
            for line in ifile.readlines():
                secmatch = SECPAT.match(line)
                if secmatch:
                    if currsect and currsect in unset:
                        # starting new section, do leftover keys
                        for key in unset[currsect]:
                            #if unset[currsect][key] is None or unset[currsect][key] == "":
                                #ofile.write('%s = \n' % key)
                            #else:
                            ofile.write('%s = %s\n' % (key, unset[currsect][key]))
                        ofile.write('\n')
                        del unset[currsect]
                    currsect = secmatch.group(1)
                    ofile.write('[%s]\n' % currsect)
                elif currsect in unset:
                    keymatch = KEYPAT.match(line)
                    if keymatch and keymatch.group(1) in unset[currsect]:
                        key = keymatch.group(1)
                        #if unset[currsect][key] is None or unset[currsect][key] == "":
                            #ofile.write('%s = \n' % key)
                        #else:
                        ofile.write('%s = %s\n' % (key, unset[currsect][key]))
                        del unset[currsect][key]
                    else:
                        ofile.write(line)
                else:
                    ofile.write(line)
            # end of file, leftover keys, sections
            if currsect in unset:
                for key in unset[currsect]:
                    #if unset[currsect][key] is None or unset[currsect][key] == "":
                        #ofile.write('%s = \n' % key)
                    #else:
                    ofile.write('%s = %s\n' % (key, unset[currsect][key]))
                ofile.write('\n')
                del unset[currsect]
            for section, vals in iteritems(unset):
                if vals:
                    ofile.write('[%s]\n' % section)
                    for key, val in iteritems(vals):
                        #if val is None or val == "":
                            #ofile.write('%s = \n' % key)
                        #else:
                        ofile.write('%s = %s\n' % (key, val))

    shutil.copy(ofile.name, inifile)
    os.unlink(ofile.name)

def merge_and_delete_params(params, inifile):
    """
    Merge input to inifile and remove entries if params specifies it.
    :param params: dictionary with keys representing sections in the
                   ini file. Values are dictionaries representing
                   parameter values within the section.
    :param inifile: File to modify.
    """
    ini_json = inifile_to_json(inifile)
    ## Compare each key value pair in sections & merge the incoming config.
    ## If there is a new section or a new key to a section, add it to the
    ## ini_json completing the merge.

    for section, conf_pair_dict in iteritems(params):
        if section not in ini_json:
            ini_json[section] = {}
        for config_name, config_value in iteritems(conf_pair_dict):
            if config_value == 'REMOVE_KEY':
                ini_json[section].pop(config_name,"")
                continue
            ini_json[section][config_name] = config_value

    ## Convert the ini json back into ini file.
    ini_obj = json_to_ini(ini_json)
    with open(inifile, "w") as fp:
        ini_obj.write(fp)
