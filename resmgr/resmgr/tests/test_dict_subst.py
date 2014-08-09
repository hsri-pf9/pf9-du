# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved

from unittest import TestCase
from resmgr.dict_subst import substitute
import json

class TestDictSubst(TestCase):

    def test_dict_substitution(self):
        a = {
            'x': 1,
            'y': {
                'a': 2,
                'b': 'foo',
                'c': 3,
                'd': 'joe'
            },
            'z': 'foo'
        }
        orig_json = json.dumps(a)
        token_map = {'foo': 'bar', 'joe': 'jane'}
        b = substitute(a, token_map)
        expected = {
            'x': 1,
            'y': {
                'a': 2,
                'b': 'bar',
                'c': 3,
                'd': 'jane'
            },
            'z': 'bar'
        }
        self.assertEqual(json.dumps(b), json.dumps(expected))
        # Ensure 'a' hasn't changed
        self.assertEqual(orig_json, json.dumps(a))
