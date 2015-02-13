#!/bin/python
# Copyright (c) 2015 Platform9 Systems Inc.

# A simple utility to query and edit json
# files. This assumes that keys are passed in
# a dot notation format.

import sys
import json
import optparse

def search(data, keys, command="query", value=None):
    """
    A depth-first search type algorithm that uses 'keys'
    to traverse the tree and print (query) or edit the
    corresponding values.

    :param data: the tree to traverse (a nested dict)
    :param keys: a list of keys to traverse
    :param command: can be one of [query|edit]
        --query: prints (to stdout) the value of 'key'
        --edit: replaces the value of 'key'
    :param value: the value to replace when editing 'key'
    """
    # if there are no keys left, then we have
    # exhausted the search path and can no longer
    # go on
    if len(keys) == 0:
        print("No such key {}".format(keys))
        exit(1)
    # if there is one key, check if it exists by
    # making sure that data is still a dict, otherwise
    # we are dealing with a nonexistent key
    elif len(keys) == 1 and isinstance(data, dict):
        if command == "query":
            print(data[keys[0]])
        elif command == "edit":
            if len(value) >= 2:
                if value[1].isdigit():
                    data[keys[0]] = int(value[1])
                else:
                    data[keys[0]] = value[1]
            else:
                print("Need value to replace key {}".format(keys))
                exit(1)
    # if there is more than one key, then we traverse
    # one level deeper
    elif isinstance(data, dict):
        key = keys.pop(0)
        search(data[key], keys, command, value)
    # a nonexistent key
    else:
        print("No such key {}".format(keys))
        exit(1)


def parse_options():
    usage="usage: %prog <file> <command> <key> [value]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-q', '--query', action='store', dest='query',
            help='List the value for the key')
    parser.add_option('-e', '--edit', action='store', dest='edit',
            help='Edit the value of the key')
    parser.add_option('-i', '--inline', action='store_true', dest='inline',
            help='Edit the file inline')

    # args[0] is the path to the json file
    # args[1] is the replacement value during an edit
    opts, args = parser.parse_args()
    return vars(opts), args

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Not enough arguments")
        exit(1)

    options, args = parse_options()

    # open read-only
    with open(args[0]) as file:
        data = json.load(file)

    for command, key in options.items():
        if type(key) is str:
            keys = key.split(".")
            search(data, keys, command, value=args)

    # if we do inline editing, open the file with the 'w' mode set.
    # we then dump the our in-memory copy of the JSON file
    if options['inline']:
        with open(args[0], 'w') as file:
            json.dump(data, file, sort_keys=True, indent=4,separators=(',',':'))
    # otherwise, output to stdout
    elif options['edit']:
        print(json.dumps(data, sort_keys=True, indent=4, separators=(',',':')))
