# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.


import copy

def substitute(dictionary, token_map):
    """
    Makes a copy of a dictionary, replaces all tokens with
    their corresponding value from the map, and returns the copy.
    """
    d = copy.deepcopy(dictionary)
    _substitute(d, token_map)
    return d

def _substitute(dictionary, token_map):
    for key, val in dictionary.iteritems():
        val_type = type(val)
        if val_type is dict:
            _substitute(val, token_map)
        elif val_type in (str, unicode) and val in token_map:
            dictionary[key] = token_map[val]

