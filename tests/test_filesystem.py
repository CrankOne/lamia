"""
Tests the filesystem routines within Lamia
"""

import os, shutil, tempfile
import unittest as UT
from lamia.core.filesystem import Paths, rxFSStruct, dict_product, \
                                  render_path_templates
from lamia.core.configuration import Stack

class TestLamiaFilesystemTemplates(UT.TestCase):
    def setUp(self):
        self.examples = [
                    "{year}",
                    "foo",
                    "one.dat"
                    "{period}@periodDir",
                    "!run-{runID}@runDir",
                    "!{variant}@varDir",
                    # A raw path separator in the (non-aliased) name itself
                    # is allowed -- the legacy escape hatch for embedding an
                    # absolute path foreign to any declared mount directly
                    # in a node name (see PathsDeployment.assure_dir_exists'
                    # warn-and-deploy-anyway fallback); prefer `mounts:'/
                    # `_mount:' for anything new.
                    "/tmpl",
                    "one/two",
                ]
        self.faultyExamples = [
                    "@",
                    "@one",
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


class TestLamiaMultiMountDeployment(UT.TestCase):
    """
    Demo/regression fixture for the multi-mount subtree deployment feature
    (`mounts:'/`_mount:' in a subtree manifest). Mimics, at toy scale, the
    AFS ("control": exec scripts, logs)/EOS ("data": everything else) split
    used by assets/fstructs/alignment.yaml, using two plain temp dirs
    standing in for the two physical filesystems.
    """
    def setUp(self):
        self.afsRoot = tempfile.mkdtemp(prefix='lamia-test-control-')
        self.eosRoot = tempfile.mkdtemp(prefix='lamia-test-data-')
        self.fStruct = {
            'mounts' : { 'control' : '$root', 'data' : '{eosWorkDir}' },
            'exec' : {
                '!run.sh@runExec' : 'run.sh content\n'
            },
            'logs@logsDir' : None,
            'work' : {
                '_mount' : 'data',
                '!input.{runID}.txt@inputFile' : 'input file content\n',
                'sub' : {
                    # dips back out to `control' despite being nested under a
                    # `data'-mounted branch
                    'logs@subLogsDir' : { '_mount' : 'control' },
                    'out@outDir' : None,
                }
            }
        }

    def tearDown(self):
        shutil.rmtree(self.afsRoot, ignore_errors=True)
        shutil.rmtree(self.eosRoot, ignore_errors=True)

    @staticmethod
    def _leaf_handler(template, destStream, path=None, context={}, contextHooks={}):
        destStream.write(template)

    def test_multi_mount_deploy(self):
        p = Paths(self.fStruct)
        pathCtx = { 'runID' : 42, 'eosWorkDir' : self.eosRoot }
        aliases = p.create_on( self.afsRoot, pathCtx=pathCtx, tContext=Stack()
                              , leafHandler=self._leaf_handler )
        # exec/ and logs/ (no _mount override) must land on the control
        # (AFS-like) root, exactly where `root' pointed
        self.assertTrue(os.path.isfile(os.path.join(self.afsRoot, 'exec', 'run.sh')))
        self.assertTrue(os.path.isdir(os.path.join(self.afsRoot, 'logs')))
        # work/'s own content (_mount: data) must land on EOS, not AFS --
        # note that AFS *does* end up with an (empty) "work/sub/" scaffold,
        # since work/sub/logs reverts to control below and a directory's
        # ancestors must exist on whichever mount actually hosts it; that's
        # an expected, harmless side effect of mirroring the full path shape
        # across mounts, not bulk content leaking onto the wrong filesystem.
        self.assertFalse(os.path.exists(os.path.join(self.afsRoot, 'work', 'input.42.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.eosRoot, 'work', 'input.42.txt')))
        # work/sub/logs dips back to control despite the data-mounted parent
        self.assertTrue(os.path.isdir(os.path.join(self.afsRoot, 'work', 'sub', 'logs')))
        self.assertFalse(os.path.exists(os.path.join(self.eosRoot, 'work', 'sub', 'logs')))
        # work/sub/out has no override of its own -- inherits `data' from `work'
        self.assertTrue(os.path.isdir(os.path.join(self.eosRoot, 'work', 'sub', 'out')))
        self.assertFalse(os.path.exists(os.path.join(self.afsRoot, 'work', 'sub', 'out')))
        # Post-deployment alias query (as engage_alignment_tasks()/q() uses
        # it) must resolve to the same, correctly mount-rooted, abs paths
        self.assertEqual( aliases['runExec'][0][0]
                         , os.path.join(self.afsRoot, 'exec', 'run.sh') )
        self.assertEqual( aliases['inputFile'][0][0]
                         , os.path.join(self.eosRoot, 'work', 'input.42.txt') )
        self.assertEqual( aliases['subLogsDir'][0][0]
                         , os.path.join(self.afsRoot, 'work', 'sub', 'logs') )
        self.assertEqual( aliases['outDir'][0][0]
                         , os.path.join(self.eosRoot, 'work', 'sub', 'out') )

    def test_alias_abspath_matches_deployment(self):
        """
        Context-hook-style resolution (Paths.__call__(alias, abspath=True),
        as used from `ctx["LAMIA.subtree"](...)' within a template context
        hook) must agree with the post-deployment alias query above.
        """
        p = Paths(self.fStruct)
        pathCtx = { 'runID' : 7, 'eosWorkDir' : self.eosRoot }
        captured = {}
        def _leaf_handler(template, destStream, path=None, context={}, contextHooks={}):
            captured['inputFile'] = p('inputFile', abspath=True, runID=7)
            captured['subLogsDir'] = p('subLogsDir', abspath=True)
            destStream.write(template)
        p.create_on( self.afsRoot, pathCtx=pathCtx, tContext=Stack()
                   , leafHandler=_leaf_handler )
        self.assertEqual( captured['inputFile']
                         , os.path.join(self.eosRoot, 'work', 'input.7.txt') )
        self.assertEqual( captured['subLogsDir']
                         , os.path.join(self.afsRoot, 'work', 'sub', 'logs') )

    def test_legacy_single_root_unaffected(self):
        """
        A manifest declaring no `mounts:' table at all must deploy exactly
        as it did before this feature existed -- single root, no surprises.
        """
        legacy = { 'exec' : { '!run.sh@runExec' : 'x' }, 'logs@logsDir' : None }
        p = Paths(legacy)
        aliases = p.create_on( self.afsRoot, pathCtx={}, tContext=Stack()
                              , leafHandler=self._leaf_handler )
        self.assertEqual( aliases['runExec'][0][0]
                         , os.path.join(self.afsRoot, 'exec', 'run.sh') )
        self.assertTrue(os.path.isdir(os.path.join(self.afsRoot, 'logs')))

    def test_abspath_before_deployment_via_resolve_mounts(self):
        """
        Regression test: abspath=True alias resolution must work BEFORE
        create_on() ever runs, given an explicit resolve_mounts() call --
        this is what a caller needs to prepare a file the deployment will
        later reference (cf. adjust_detsdat_for_runs() resolving
        `@localDetsDat' ahead of subtree deployment). Before this fix,
        Paths.__call__(..., abspath=True) raised RuntimeError here, since
        _resolvedRoots was only ever populated from inside create_on().
        """
        p = Paths(self.fStruct)
        pathCtx = { 'runID' : 42, 'eosWorkDir' : self.eosRoot }
        p.resolve_mounts( self.afsRoot, pathCtx )
        self.assertEqual( p('inputFile', abspath=True, **pathCtx)
                         , os.path.join(self.eosRoot, 'work', 'input.42.txt') )
        self.assertEqual( p('runExec', abspath=True, **pathCtx)
                         , os.path.join(self.afsRoot, 'exec', 'run.sh') )
        # And a later create_on() pass still deploys correctly (resolving
        # mounts again internally is idempotent, not a conflict).
        aliases = p.create_on( self.afsRoot, pathCtx=pathCtx, tContext=Stack()
                              , leafHandler=self._leaf_handler )
        self.assertEqual( aliases['inputFile'][0][0]
                         , os.path.join(self.eosRoot, 'work', 'input.42.txt') )

    def test_abspath_without_resolve_mounts_raises_clearly(self):
        """ The pre-fix failure mode should still fail loudly, not silently. """
        p = Paths(self.fStruct)
        with self.assertRaises(RuntimeError):
            p('inputFile', abspath=True, runID=42, eosWorkDir=self.eosRoot)

    def test_legacy_foreign_absolute_path_warns_not_raises(self):
        """
        A node name embedding a raw absolute path outside every declared
        mount (the pre-`mounts:' hack still used by some fstructs, e.g.
        `"/eos/.../{tag}@trafOutDir"') must still deploy there directly,
        with a warning, rather than crashing outright -- restoring behavior
        from before the multi-mount rewrite.
        """
        foreignRoot = tempfile.mkdtemp(prefix='lamia-test-foreign-')
        try:
            fStruct = dict(self.fStruct)
            fStruct['foreign'] = {
                '{}@foreignDir'.format(os.path.join(foreignRoot, 'out')) : None
            }
            p = Paths(fStruct)
            pathCtx = { 'runID' : 1, 'eosWorkDir' : self.eosRoot }
            with self.assertLogs(level='WARNING') as logs:
                aliases = p.create_on( self.afsRoot, pathCtx=pathCtx, tContext=Stack()
                                      , leafHandler=self._leaf_handler )
            self.assertTrue(any('not within mount' in m for m in logs.output))
            self.assertEqual( aliases['foreignDir'][0][0]
                             , os.path.join(foreignRoot, 'out') )
            self.assertTrue(os.path.isdir(os.path.join(foreignRoot, 'out')))
        finally:
            shutil.rmtree(foreignRoot, ignore_errors=True)

    def test_unknown_mount_reference_raises(self):
        """ A `_mount:' referencing an undeclared label fails loudly. """
        bad = dict(self.fStruct)
        bad['exec'] = { '_mount' : 'nope', '!run.sh@runExec' : 'x' }
        p = Paths(bad)
        with self.assertRaises(KeyError):
            p.create_on( self.afsRoot, pathCtx={'eosWorkDir': self.eosRoot}
                       , tContext=Stack(), leafHandler=self._leaf_handler )
