"""
Unit test for string interpolation.
"""

import unittest as UT
from lamia.core.interpolation import Processor as StringProc
from lamia.core.interpolation import DictInterpolator


gSubstDict = { '1' : 'one'
     , 'two' : '2'
     , 'null' : ''
     , '' : 'nothing'
     , 'fourtyTwo' : 42
     , 'natnums' : [1, 2, 3]
     , 'someSet' : set({'foo', 'bar'})
     , 'dict' : { 'some' : 12, 'thing' : 'thirteen' }
     , 'e\\$cape\\(test' : 'ok'
     , 'recursive' : '$(SMPL:recursive)'
     , 'recursive1' : '$(SMPL:recursive2)'
     , 'recursive2' : '$(SMPL:recursive1)'
     }

class FaultyInterpolation(object):
    """
    Faulty interpolator returns None that has to be considered as an error.
    """
    def __init__(self):
        pass

    def __call__(self, v):
        pass


class MockIntepolation(object):
    """
    Mock interpolator just memorizes given values, returning them
    not modified.
    """
    def __init__(self):
        self.matches = {}

    def __call__(self, v, key=None):
        self.matches[key] = v
        return v


class ProcessorStr_TestCase(UT.TestCase):
    def setUp(self):
        self.pb = StringProc()
        self.pb['MOCK'] = MockIntepolation()
        self.pb['FLTY'] = FaultyInterpolation()
        self.pb['SMPL'] = DictInterpolator(gSubstDict)
        self.pb['LMBD'] = lambda x : "I'm a lambda " + x
        self.initialStruct = {
                    'one' : [ 'keep $(MOCK:this)', 'fix $(SMPL:null)this' ],
                    'two' : {
                        'one' : { 'a' : '$(MOCK:)' },
                        'b' : 'keep as is'
                    },
                    'three' : set(['$(SMPL:1)', 'two'])
                }
        self.structToCheck = {
                    'one' : [ 'keep this', 'fix this' ],
                    'two' : {
                        'one' : { 'a' : '' },
                        'b' : 'keep as is'
                    },
                    'three' : set(['one', 'two'])
                }

    def test_simple_capture(self):
        self.assertEqual( 'this must remain'
                        , self.pb('$(MOCK:this must remain)') )

    def test_not_found(self):
        with self.assertRaises(KeyError):
            self.pb('$(MOZK:faulty reference)')

    def test_faulty_interpolator(self):
        with self.assertRaises(RuntimeError):
            self.pb('$(FLTY:returns None.)')

    def test_proper(self):
        self.assertEqual( '1 is one', self.pb('1 is $(SMPL:1)') )
        self.assertEqual( 'two is 2', self.pb('two is $(SMPL:two)') )
        self.assertEqual( '"" gives empty', self.pb('"$(SMPL:null)" gives empty') )
        self.assertEqual( 'nothing here', self.pb('$(SMPL:) here') )

    def test_labda_interpolator(self):
        self.assertEqual( "I'm a lambda result", self.pb("$(LMBD:result)") )

    def test_struct_interp(self):
        a, b = self.pb( self.initialStruct ), self.structToCheck
        self.assertEqual( a['one'][0], b['one'][0] )
        self.assertEqual( a['one'][1], b['one'][1] )
        self.assertEqual( a['two']['one']['a'], b['two']['one']['a'] )
        self.assertEqual( a['two']['b'], b['two']['b'] )
        self.assertEqual( a['three'], b['three'] )

    def test_few_interp(self):
        self.assertEqual( self.pb( '$(SMPL:1)/$(SMPL:two)$(SMPL:null)/$(SMPL:)' )
                        , 'one/2/nothing' )

    def test_escaping(self):
        self.assertEqual( self.pb( '$(SMPL:e\\$cape\\(test)' ), 'ok' )

    def test_recursion_detection(self):
        with self.assertRaises(RecursionError):
            self.pb( '$(SMPL:recursive)' )
        with self.assertRaises(RecursionError):
            self.pb( '$(SMPL:recursive1)' )

class ProcessorVarTypes_TestCase(UT.TestCase):
    def setUp(self):
        self.pb = StringProc()
        self.pb['SMPL'] = DictInterpolator(gSubstDict)
        self.structToSubst = {
                    'intTyped' : '$(SMPL:fourtyTwo)',
                    'someLst' : '$(SMPL:natnums)',
                    'someDct' : '$(SMPL:dict)',
                    'setHere' : '$(SMPL:someSet)'
                }
        self.chck = self.pb( self.structToSubst )

    def test_int_subst(self):
        self.assertEqual( self.chck['intTyped'], 42 )

    def test_lst_subst(self):
        self.assertEqual( self.chck['someLst'], [1, 2, 3] )

    def test_dct_subst(self):
        self.assertEqual( self.chck['someDct'], self.pb['SMPL']['dict'] )

    def test_set_subst(self):
        self.assertEqual( self.chck['setHere'], self.pb['SMPL']['someSet'] )

