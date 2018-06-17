"""
Tests the merging of configuration dictionaries
"""

# TODO: disabled for a while ...

#import unittest as UT
#from lamia.core.templates import Loader, Templates
#import lamia.core.configuration as LC
#import lamia.core.interpolation as LI
#
#TMPLTS_DIR='test'
#
#class TemplatesTest(UT.TestCase):
#    """
#    The assets/templates dir has to be present with at least root.yaml and
#    test.yaml templates within.
#    """
#    def setUp(self):
#        self.chckDct = { 'one' : 1, 'two' : 'three', 'four' : [5, 6] }
#        self.cp = LI.Processor()
#        self.cp['TST'] = lambda k : self.chckDct[k]
#        self.l = Loader(TMPLTS_DIR, interpolators=self.cp)
#        self.t = Templates([TMPLTS_DIR], loaderInterpolators=self.cp)
#
#    def test_loader(self):
#        self.assertTrue( type(self.l.templates['test'][0]) is LC.Configuration )
#        self.assertEqual( self.l.templates['test'][0]['test']['aliasDiscovered']
#                        , 'here must be an aliased content')
#        for k, v in self.l.templates['test'][0]['test']['customInterpTest'].items():
#            self.assertEqual( v, self.chckDct[k] )
#
#    def test_rendering(self):
#        self.assertEqual( 'trivial', self.t('test') )
