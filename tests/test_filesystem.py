"""
Tests the filesystem routines within Lamia
"""

import os, shutil
import unittest as UT
from lamia.core.filesystem import Paths, rxFSStruct, dict_product, \
                                  render_path_templates

class TestLamiaFilesystemTemplates(UT.TestCase):
    def setUp(self):
        self.examples = [
                    "{year}",
                    "foo",
                    "one.dat"
                    "{period}@periodDir",
                    "!run-{runID}@runDir",
                    "!{variant}@varDir",
                ]
        self.faultyExamples = [
                    "@",
                    "@one",
                    "/tmpl",
                    "one/two",
                    "sdf@so/me",
                    "ho.rizeon@so.m"
                ]
        self.pStruct = {
                "rootDir-{year}@root" : {
                    "some" : {
                        "!other.dat@other-file" : 'some/template/here'
                        }
                    }
                }

    def test_generic_match(self):
        for expr in self.examples:
            m = rxFSStruct.match(expr)
            self.assertTrue(m)
        for expr in self.faultyExamples:
            m = rxFSStruct.match(expr)
            self.assertFalse(m)

    def test_paths(self):
        p = Paths(self.pStruct)
        self.assertEqual( 'rootDir-1983/some/other.dat'
                , p('other-file', year=1983) )

class TestLamiaFilesysRoutines(UT.TestCase):
    """
    UT test case utilizing Lamia's filesystem routines.
    TODO: involve @permissions
    """
    def setUp(self):
        self.testFStruct = { 'lamiaTest' : {
                'one' : None,
                '{some}' : {
                    '{thing}' : None,
                    '@tag' : 'something',
                    '{within}' : { '@tag' : 'something within' }
                }
            } }
        self.chck = { 'lamiaTest' : {
                'one' : None,
                'two' : {
                    'three' : None,
                    '@tag' : 'something',
                    'four' : { '@tag' : 'something within' }
                }
            } }
        self.chkTags = { 'something within' : ['lamiaTest', '{some}', '{within}']
                       , 'something' : ['lamiaTest', '{some}'] }

class TestLamiaDictProducts(UT.TestCase):
    def setUp(self):
        pass

    def test_seq_interp_single(self):
        cChk = set([1, 2, 3])
        for r in dict_product( a=1, b=2, c=[1, 2, 3], d=1.23 ):
            self.assertEqual( len(r), 4 )
            self.assertEqual( r['a'], 1 )
            self.assertEqual( r['b'], 2 )
            self.assertEqual( r['d'], 1.23 )
            self.assertTrue( r['c'] in cChk )
            cChk.remove(r['c'])
        self.assertFalse(len(cChk))

    def test_seq_interp_few(self):
        cChk1 = set([1, 2, 3])
        cChk2 = set(['ab', 'bc'])
        for r in dict_product( one=set(['ab', 'bc']), a=1, b=2, c=[1, 2, 3], d=1.23 ):
            self.assertEqual( len(r), 5 )
            self.assertEqual( r['a'], 1 )
            self.assertEqual( r['b'], 2 )
            self.assertEqual( r['d'], 1.23 )
            self.assertTrue( r['c'] in cChk1 )
            self.assertTrue( r['one'] in cChk2 )

    def test_trivial_product(self):
        wasThere = False
        for r in dict_product( ):
            wasThere = True
        self.assertTrue(wasThere)
        wasThere = False
        for r in dict_product( single=1 ):
            self.assertEqual( r['single'], 1 )
            wasThere = True
        self.assertTrue(wasThere)

class TestLamiaPathInterp(UT.TestCase):
    def setUp(self):
        self.template = [ 'root', 'iter#{itNo}', 'subFile.{sfID}' ]
        self.check = set([
                'root/iter#2/subFile.uno',
                'root/iter#2/subFile.dos',
                'root/iter#2/subFile.tres',
                'root/iter#1/subFile.uno',
                'root/iter#1/subFile.dos',
                'root/iter#1/subFile.tres',
            ])

    def test_path_interp(self):
        """ Tests general substitution validity. """
        for p, argsSet in render_path_templates( *self.template, itNo=[1, 2], sfID=['uno', 'dos', 'tres'] ):
            self.assertTrue(p in self.check)
            self.check.remove(p)
        self.assertFalse(len(self.check))

    def test_path_interp_no_duplicates(self):
        met = set()
        for p, argsSet in render_path_templates( *self.template[:2], itNo=[1, 2], sfID=['uno', 'dos', 'tres'] ):
            self.assertTrue( p not in met )
            met.add( p )
        self.assertEqual( len(met), 2 )
