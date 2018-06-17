"""
Tests the merging of configuration dictionaries
"""

import unittest as UT
from lamia.core.configuration import Configuration \
                                   , Stack as ConfigurationStack

#
# Confs

class ConfigurationSimpleCaseSubst(UT.TestCase):
    """
    Test simple configuration subst interpolation.
    """
    def setUp(self):
        self.cfg = Configuration("""
        some: one
        another: $(value:some)
        """)

    def test_simple(self):
        self.assertTrue(self.cfg['another'], 'one')


class ConfigurationSwitches(UT.TestCase):
    def setUp(self):
        self.cfg = Configuration({
                'variants' : {
                    'default' : [1, 2, 3],
                    'reversed' : [3, 2, 1]
                }
                }, switches={'variants' : ('reversed', 'choosen') })

    def test_switch_done(self):
        self.assertEqual( self.cfg['choosen'], [3, 2, 1] )
        self.assertEqual( 1, len(self.cfg) )

class ConfigurationHierarchicalSubst(UT.TestCase):
    """
    Test in-depth configuration subst interpolation.
    """
    def setUp(self):
        self.cfg = Configuration("""
        root:
            one: 'one'
            two:
                one: $(value:root.one)
        """)
    def test_depth(self):
        self.assertTrue(self.cfg['root.two.one'], 'one')

class ConfigurationHierarchicalSubstAdvanced(UT.TestCase):
    """
    Test in-depth configuration subst interpolation with
    appending/excluding/subtracting.
    """
    def setUp(self):
        self.cfg = Configuration("""
        root:
            one: ['a', 'b', 'c']
            two:
                one: $(value:root.one)
        """)

    def test_depth(self):
        self.assertTrue(self.cfg['root.two.one'], [1, 2, 3])

class ConfigurationCopyBehaviour(UT.TestCase):
    def setUp(self):
        self.cfg = Configuration({
                'one' : None
            })

    def test_set(self):
        obj = [1, 2]
        dct = {}
        dct['foo'] = obj
        self.cfg['two'] = obj
        #self.assertEqual( self.cfg['two'] is obj, dct['foo'] is obj )

class ConfigurationHierarchicalLookup(UT.TestCase):
    def setUp(self):
        self.cfg = Configuration({
                'one' : 1,
                'two' : {
                    'n-half' : [1, 2],
                    'n-thirds' : [1, 3]
                }
            })

    def test_presense( self ):
        self.assertTrue( 'one' in self.cfg )
        self.assertTrue( 'two' in self.cfg )
        self.assertTrue( 'two.n-half' in self.cfg )
        self.assertTrue( 'two.n-thirds' in self.cfg )
        self.assertFalse( 'two.n-fourths' in self.cfg )

#
# Stacked Confs

class ConfigurationStackTest(UT.TestCase):
    def setUp(self):
        self.stack = ConfigurationStack()
        self.dct = { 'one' : 1
                   , 'two' : 3
                   , 'foo' : 'bar'
                   , 'some' : { 'where' : 'here' } }
        self.stack.push( self.dct )

    def test_basic_retrieval(self):
        self.assertTrue( 'one' in self.stack )
        self.assertTrue( self.stack['one'], 1 )
        self.assertTrue( 'some.where' in self.stack )

    def test_basic_overriden_retrieval(self):
        self.stack.push( { 'two' : 2 } )
        self.assertTrue( self.stack['two'], 2 )
        self.assertEqual( 4, len(self.stack) )
        del(self.stack['two'])
        self.assertEqual( 3, len(self.stack) )
        self.stack.pop()
        self.assertEqual( self.stack['two'], 3 )
        self.assertEqual( 4, len(self.stack) )

    def test_basic_iteration(self):
        chck = set({'one', 'two', 'foo', 'some'})
        for k, v in self.stack.items():
            chck.remove(k)
            self.assertEqual( self.dct[k], v )
        self.assertFalse( chck )
        # Check, that we had preserved the original dictionary
        self.assertTrue( self.dct )

    def test_overriden_retrieval(self):
        self.stack.push( {'one' : [2, 15], 'bar' : {'twelve' : 12, 'thirteen' : 13} } )
        self.assertTrue( 'one' in self.stack.keys() )
        self.assertEqual( self.stack['one'], [2, 15] )
        self.assertEqual( self.stack['bar'], {'twelve' : 12, 'thirteen' : 13} )
        self.assertTrue( 'bar.thirteen' in self.stack )
        self.assertFalse( 'bar.fourteen' in self.stack )
        self.assertTrue( 'one.1' in self.stack )
        del( self.stack['one'] )
        self.assertFalse( 'one' in self.stack )
        self.assertFalse( 'one.1' in self.stack )
        self.stack.pop()
        self.test_basic_retrieval()

    def test_overriden_iteration(self):
        self.assertEqual( 4, len(self.stack) )
        self.stack.push( {'one' : [2, 15], 'bar' : {'twelve' : 12, 'thirteen' : 13} } )
        self.assertEqual( 5, len(self.stack) )
        chk = set({ 'one', 'two', 'foo', 'bar', 'some' })
        for k, v in self.stack.items():
            self.assertTrue( k in chk )
            chk.remove(k)
        self.assertFalse(chk)
        # ... whatever
