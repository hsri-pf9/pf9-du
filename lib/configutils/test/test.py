# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import os

from configutils import configutils

_basedir = os.path.dirname(os.path.realpath(__file__))
VALIDJSON = os.path.join(_basedir, "valid.json")
VALIDDEFAULTJSON = os.path.join(_basedir, "valid_default.json")
VALIDINI = os.path.join(_basedir, "valid.ini")
VALIDDEFAULTINI=os.path.join(_basedir, "valid_default.ini")
NESTEDJSON = os.path.join(_basedir, "nested.json")
NOSECTIONJSON = os.path.join(_basedir, "nosection.json")
INVALIDJSON = os.path.join(_basedir, "invalid.json")



def _no_file_test(method):
    nofilecheck = False
    try:
        method("nofile")
    except Exception, e:
        nofilecheck = True
        assert type(e) == OSError
        assert e.errno == 2

    assert nofilecheck


def _json_error_test(filename, exc):
    exccheck = False
    try:
        configutils.jsonfile_to_ini(filename)
    except Exception, e:
        exccheck = True
        assert type(e) == exc

    assert exccheck


def test_jsonfile_to_ini():
    # File doesn't exist
    _no_file_test(configutils.jsonfile_to_ini)

    # Valid JSON
    inicfg = configutils.jsonfile_to_ini(VALIDJSON)
    assert set(inicfg.sections()) == set(["key1", "key2", "key3"])
    assert inicfg.items("key1") == [('subkey2', 'subval2'), ('subkey1', 'subval1')]
    assert inicfg.items("key3") == [('subkey4', 'subval4')]

    # Valid JSON with default
    inicfg = configutils.jsonfile_to_ini(VALIDDEFAULTJSON)
    assert set(inicfg.sections()) == set(["key2", "key3"])
    assert inicfg.defaults()["subkey2"] == "subval2"

    # Bad JSON
    _json_error_test(INVALIDJSON, ValueError)

    # Nested JSON
    _json_error_test(NESTEDJSON, configutils.NestedSectionError)

    # Missing section JSON
    _json_error_test(NOSECTIONJSON, configutils.MissingSectionError)


def test_inifile_to_json():
    # File doesn't exist
    _no_file_test(configutils.inifile_to_json)

    # Valid INI
    jsoncfg = configutils.inifile_to_json(VALIDINI)
    assert jsoncfg["section1"]["key1"] == "var1"
    assert jsoncfg["section2"]["key3"] == "5.25"

    # Valid INI with default
    jsoncfg = configutils.inifile_to_json(VALIDDEFAULTINI)
    assert jsoncfg["section2"]["key4"] == '"%(key1)s"'
    assert "key1" not in jsoncfg["section2"].keys()


def test_is_dict_subset():
    # Dict, identical
    d1 = {'a': 2, 3: 'b', 4:'c'}
    d2 = {3: 'b', 4:'c'}
    assert configutils.is_dict_subset(d2, d1)
    # Dict, non identical
    d1 = {'a': 2, 3: 'b', 4:'c'}
    d2 = {3: 'b', 4: 'd'}
    assert not configutils.is_dict_subset(d2, d1)
    # Dict, with list, identical but unsupported list
    d1 = {'a': 2, 3: ['b', 'c']}
    d2 = {3: ['b', 'c']}
    assert not configutils.is_dict_subset(d2, d1)
    # Nested dict, identical subdict
    d1 = {'a': 2, 3: {5: {'b': 'c'}}}
    d2 = {3: {5: {'b': 'c'}}}
    # Nested dict, subdict is a superset
    d1 = {'a': 2, 3: {5: {'b': 'c', 'd': 'e'}}}
    d2 = {3: {5: {'b': 'c'}}}
    assert configutils.is_dict_subset(d2, d1)
    # Nested dict, differ by type, OK because 4 == 4.0
    d1 = {'a': 2, 3: {5: {5: 4.0}}}
    d2 = {3: {5: {5: 4}}}
    assert configutils.is_dict_subset(d2, d1)
