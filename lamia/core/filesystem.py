# -*- coding: utf-8 -*-
# Copyright (c) 2018 Renat R. Dusaev <crank@qcrypt.org>
# Author: Renat R. Dusaev <crank@qcrypt.org>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Various auxilliary filesystem routines, coming in hand for lamia procedures.
"""
import os, sys, errno, collections, re, dpath, yaml, itertools, logging, copy \
     , glob, contextlib, argparse, io, bidict, json
import lamia.core.interpolation, lamia.core.configuration, lamia.confirm
from enum import Enum
from string import Formatter

rxsFSStruct = r'^(?P<isFile>!?)(?P<nmTmpl>[^@\n]+)(?:@(?P<alias>[_\-\w]+))?$'
rxFSStruct = re.compile(rxsFSStruct)
rxFmtPat = re.compile(r'\{[^}\s]+\}')

# Default access mode for files created.
DFTFMOD = 0o664  # TODO: use

#
# Exceptions

class BadPathTemplate(ValueError):
    """
    The malformed path template token(s) met.
    """
    pass

class BadFileDescription(ValueError):
    """
    The file description is not valid.
    """
    pass

class IncompleteContext(KeyError):
    """
    The template rendering context is not complete and this is not expected.
    """
    pass

class DulicatingAlias(KeyError):
    """
    Duplicating alias name found.
    """
    pass

#
# Routines

def _is_seq(v):
    if isinstance( v, tuple ) \
    or isinstance( v, list ) \
    or isinstance( v, set ):
        return True
    return False

def dict_product(**kwargs):
    """
    Returns an iterator to the dictionaries set obtained from given one by
    splitting out (product) of element's components. E.g. the
    kwargs={one:[1, 2], two:[3,4]} will yield:
        {one:1, two:3}
        {one:1, two:4}
        {one:2, two:3}
        {one:2, two:4}
    Order is not guaranteed.
    TODO: support for nested dicts/sequences.
    """
    L = logging.getLogger(__name__)
    scalars = {}
    sequences = {}
    callables = {}
    # Iterate over keyword arguments to sort out the scalar values, sequences
    # and callable objects (that may, in order, yield either a scalar or
    # sequence).
    for k, v in kwargs.items():
        if _is_seq(v):
            sequences[k] = v
            if any( map( lambda x: type(x) not in (bool, int, float, str)
                       , v )
                  ):
                raise NotImplementedError("Nested sequences aren't"
                        " yet supported.")  # TODO
        elif type(v) in (bool, int, float, str):
            scalars[k] = v
        elif callable(v):
            callables[k] = v
        else:
            raise TypeError('%s: %s'%(k, type(v).__name__))
    keys = sequences.keys()
    vals = sequences.values()
    # Obtain cartesian products of all the sequences, evolving them into scalar
    # values. With each comination of scalar values derived from the product,
    # compose the "plain" dictionary and use it with callables to yield the
    # callables results.
    for instance in itertools.product(*vals):
        assert(len(keys) == len(instance))  # cohesiveness of product and keys
        dct = dict(zip(keys, instance))
        dct.update(scalars)  # update product result with scalars
        if not callables:
            yield dct  # No callables -> just yield the plain dict
        else:
            # Fill the callable results
            callableAppendix = {}
            for ck, c in callables.items():
                callableAppendix[ck] = c(dct)
            # Update the plain dict with callable result and recursively
            # compute product on them
            dct.update(callableAppendix)
            yield from dict_product(**dct)

# This strightforward inplementation seems legit, but needs more checks
# against Python's conventions within complex keys indexing.
def py_index_to_pdict(k):
    if '[' not in k:
        return k
    else:
        k = k.replace('[', '.')
        k = k.replace(']', '')
        return k

def _rv_value(d, k, requireComplete=True):
    """
    Internal parsing function dealing with format-like indexing, e.g.:
        some[1]
        foo[bar][1]
        some[other]
    etc.
    """
    key = py_index_to_pdict(k)
    r = dpath.util.search( d, key, separator='.' )
    if r:
        return dpath.get(d, key, separator='.')
    elif not requireComplete:
        return '{%s}'%k  # NOTE: was `return k', check side effects
    else:
        raise KeyError(k)

# TODO: rename to 'render_path_template' (without 's') since the *args are
# joined and current name is unprecise and misleading
def render_path_templates(*args, requireComplete=True, **kwargs):
    """
    Renders the path according to given list of templated string and formatting
    arguments.
    Note, that in case of redundant kwargs, it will produce duplicating paths,
    so user code must get rid of them.
    """
    L = logging.getLogger(__name__)
    L.debug('Generating path templates product on sets: {%s}; {%s}.'%(
          ', '.join([ '"%s"'%s for s in args])
        , ', '.join([ '"%s"'%s for s in kwargs.keys()]) ))
    s = os.path.join(*args)
    # `keys' is a list of tokens extracted from string
    keys = list(filter( lambda tok: tok, [i[1] for i in Formatter().parse(s)]))
    #for k in keys:
    #    if _rv_value(kwargs, k, requireComplete=False) not in kwargs:
    #        s = 'Insufficient path-rendering context. Key: "%s".'%k
    #        if requireComplete:
    #            raise KeyError(s)
    #        else:
    #            L.debug(s)
    try:
        products = { k : _rv_value(kwargs, k, requireComplete=requireComplete) \
                     for k in keys }
        for cProd in dict_product(**products):
            dfw = DictFormatWrapper( **dict(cProd), requireComplete=requireComplete )
            try:
                np = s.format_map(dfw)
                yield np, cProd
            except:
                L.error( 'During substitution of product result'
                    ' {subKWArgs}, turned in formatting dict with'
                    ' keys {prKeys}.'.format(
                        subKWArgs=', '.join(['"%s"'%skwa for skwa in cProd]),
                        prKeys=', '.join(['"%s"'%k for k in dfw.keys()]) )
                    )
                raise
    except:
        L.error( 'During yielding the path %s (extracted keys are {%s},'
            ' submitted context keys: {%s}).'%( s
                , ', '.join(['"%s"'%k for k in keys])
                , ', '.join(['"%s"'%k for k in kwargs.keys()]) ) )
        raise

def check_dir( path, mode=None ):
    """
    Ensures that directory exists and, optionally, has proper access rights.
    If dir doesn't exist, it will be created either with 0o777, or with given
    mode permissions.
    TODO: If mode is None, no mode check is performed.
    """
    try:
        os.makedirs( path )
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            return False
        else:
            raise
    return True

def get_path_meanings( path, basedir=None, recursive=False, rxStr=None ):
    """
    This function performs extraction of the files by given path. The path is
    interpreted as a Unix shell-like wildcard (using `glob' module) yielding
    the list of file path that further will parsed against the given regular
    expression to extract some additional semantics (run switches, iteration
    number, etc).
    If basedir is given, the cwd will be set to this path prior to performing
    glob matching (so this arg only has sense if at least one of the `path'
    is relative).
    """
    if rxStr is not None:
        rx = re.compile(rxStr)
    else:
        rx = None
    with contextlib.ExitStack() as stack:
        if basedir is not None:
            stack.enter_context( lamia.core.filesystem.pushd( basedir ) )
        for im in glob.iglob( path, recursive=recursive ):
            if rx is None:
                yield im, None
            else:
                m = rx.match( im )
                if m:
                    yield im, m.groupdict()
                else:
                    continue

# Note: from pushd/popd, used this nice snippet:
#  https://gist.github.com/howardhamilton/537e13179489d6896dd3
@contextlib.contextmanager
def pushd(newDir):
    L = logging.getLogger(__name__)
    prevDir = os.getcwd()
    os.chdir(newDir)
    L.debug( 'pushd(%s)'%newDir )
    try:
        yield
    finally:
        L.debug( 'popd(%s)'%prevDir )
        os.chdir(prevDir)

# Custom wrapper to consider stdout as file descriptor. Helps to avoid
# duplication in cases when user code may specify stdout ('-') as an output
# location. Based on:
@contextlib.contextmanager
def smart_open(filename=None, mode='w'):
    if filename and filename != '-':
        fh = open(filename, mode)
    elif '-' == filename and 'w' in mode:
        fh = sys.stdout
    elif '-' == filename and 'r' in mode:
        fh = sys.stdin
    else:
        raise ValueError( "Unable to open \"%s\" on '%s' mode."%(filename, mode) )
    try:
        yield fh
    finally:
        if fh is not sys.stdout and fh is not sys.stdin:
            fh.close()

class DictFormatWrapper(dict):
    """
    Auxilliary class performing python formatting arguments interpolation.
    May not throw exception when missed key requested if requireComplete
    is False.
    """
    def __init__(self, *args, **kwargs):
        self.requireComplete=kwargs.pop('requireComplete', True)
        kws_ = {}
        for k, v in kwargs.items():
            dpath.new( kws_, py_index_to_pdict(k), v, separator='.' )
        super().__init__(*args, **kws_)

    def __missing__(self, key):
        L = logging.getLogger(__name__)
        #if dpath.get(key):
        if self.requireComplete:
            L.debug('Keys in context: %s'%(', '.join(self.keys())))
            raise IncompleteContext( key )
        else:
            return '{%s}'%key

class FileHandlerContextManager(object):
    """
    Context manager tracking the created file instances.
    """

    def __init__( self, path, createdRef, globContextRef, locContextRef
                , subtree, creationMode=None, alias=None ):
        assert(isinstance(globContextRef, lamia.core.configuration.Stack))
        self.createdRef = createdRef
        self.gCtxRef = globContextRef
        self.lCtxRef = locContextRef
        self._path = path
        self._subtree = subtree
        self._file = None
        self._creationMode = creationMode
        self._alias = alias

    def __enter__(self):
        self.gCtxRef.push(
                { 'LAMIA' : {
                    'path' : self._path,  # (former ?)
                    'pathContext' : self.lCtxRef,  # (former __p)
                    'subtree' : self._subtree  # (former paths)
                    }
                } , tag='runtime-path-vars' )
        # Take care of the entites that are not presented in current
        # context within the runtime stack (explicitly mark them as
        # deleted) since path context shall contain ONLY the keys
        # consumed within current path.
        #for pathKey in self.gCtxRef.keys():
        #    if pathKey not in self.lCtxRef.keys():
        #        del self.gCtxRef[pathKey]
        # ^^^ TODO: do we really need that? The mutation happens within topmost
        # conf of the Stack (when it is a Stack), so changes will be denied by
        # pop() except for case of nested dicts/lists
        assert(self._file is None)
        self._file = io.StringIO()
        return self.gCtxRef, self._file

    def write_rendered(self):
        L = logging.getLogger(__name__)
        dirPath, filename = os.path.split(self._path)
        # NOTE: this assure may take place before parent dir will be created.
        # In this case, when parent dir(s) have aliases, the won't be indexed
        # as instantiated alis. Despito of this, when the subsequnet assure..()
        # will happen, the missed aliased dirs will be injected, though.
        self.createdRef.assure_dir_exists( dirPath, self.lCtxRef )
        if os.path.exists( self._path ):
            while not self.createdRef.mode == PathsDeployment.Operation.OVERWRITE:
                uChs = lamia.confirm.ask_for_variants( 'File "%s" exists.'%self._path, {
                        'O' : 'overwrite',
                        'd' : 'show diff',
                        'A' : 'overwrite all',
                        'c' : 'cancel deployment procedure and exit',
                        's' : 'keep this file intact',
                        'e' : 'cancel subtree deployment, but explore all the diffs'
                    }, default='c' )
                if 'A' == uChs:
                    self.createdRef.mode = PathsDeployment.Operation.OVERWRITE
                elif 'd' == uChs:
                    self.show_file_diff()  # continues the loop
                elif 'O' == uChs:
                    break
                elif 'c' == uChs:
                    raise RuntimeError('Deployment cancelled due to'
                            ' file collision: "%s".'%self._path )
                elif 's' == uChs:
                    L.info('File "%s" kept intact.'%self._path)
                    return False  # `no-file-created' exit
                elif 'e' == uChs:
                    L.info('File "%s" kept intact. Resuming in'
                            ' display-diff mode.'%self._path)
                    self.createdRef.mode = PathsDeployment.Operation.EXTRACT_DIFFS
                    self.show_file_diff()
                    return False  # `no-file-created' exit
        with open(self._path, 'w') as f:
            f.write(self._file.getvalue())
        if self._creationMode:
            os.chmod( self._path, self._creationMode )
        if self._alias:
            self.createdRef.alias_instantiated( self._alias, self._path, self.lCtxRef )
        return True

    def show_file_diff(self):
        if not os.path.exists(self._path):
            L.info( 'New file "%s" to be created.'%self._path )
            # ______ BEGIN of detectors.dat diff log ______ ???
            raise NotImplementedError('Do something with the new file content.')
        else:
            raise NotImplementedError('Show file diff.')

    def __exit__(self, excType, excValue, traceBack):
        L = logging.getLogger(__name__)
        self.gCtxRef.pop( tag='runtime-path-vars' )
        if excType is None:
            cl = len(self._file.getvalue())
            L.debug( 'Rendered content for "{path}" of size {size}.'.format(
                path=self._path, size=cl) )
            if PathsDeployment.Operation.GENERATE == self.createdRef.mode \
            or PathsDeployment.Operation.OVERWRITE == self.createdRef.mode :
                if self.write_rendered():
                    self.createdRef.add_created_file(self._path, self.lCtxRef)
                    L.debug( ' .."{path}" of {size} bytes'.format(
                        path=self._path, size=cl) )
            elif PathsDeployment.Operation.EXTRACT_DIFFS:
                self.show_file_diff()
        else:
            L.error( 'Failed to render content for "%s".'%self._path )
        #self._file.close()

class PathsDeployment(object):
    """
    Stores information about filesystem entries being visited, created,
    updated, etc. Used to inspect the ongoing process and to clean-up the
    entities just being created in case of something goes wrong.
    The instances are not reentrant and have to be re-created on re-deployment.
    """
    class Operation(Enum):
        OVERWRITE = 0x1
        GENERATE = 0x2
        EXTRACT_DIFFS = 0x4

    @staticmethod
    def alias_for( aliases, **kwargs ):
        """
        A recursive picker for aliases, choosen by some criteria. Useful to
        filter out aliases by context variables.
        For practical usage one might be interested rather in
        closure-generating alias_query() static method.
        """
        if not kwargs: return aliases
        kw = next(iter(kwargs.keys()))
        v = kwargs.pop(kw)
        als = list(filter( lambda e: kw in e[1] and v == e[1][kw], aliases ))
        return PathsDeployment.alias_for(als, **kwargs)

    @staticmethod
    def alias_query( aliases ):
        """
        One may easily instantiate a simple filtering getter on the set of
        aliases. Example
            q = PathsDeployment.alias_query( myAliases )
            q('logs', runID=12, iterNo=21)
        """
        def _alias_query_concrete(nm, **kwargs):
            return PathsDeployment.alias_for( aliases[nm], **kwargs )
        return _alias_query_concrete

    def __init__(self, root, subtree, mode=Operation.GENERATE ):
        """
        Creates the new deployment object. The `root' is required to be a
        string path pointing to the base directory, where the subtree has to
        be deployed.
        """
        assert(type(root) is str)
        # list of path (as strings) being visited
        self.visited = set()
        # filesystem subtree dict-like tree of entities being created
        self._created = collections.OrderedDict()
        # current list of path tokens, stacked during recursive traversal
        self._path = []
        # base directory for deployment (filesystem subtree prefix)
        self.root = os.path.realpath( root )
        # Reference to currently processed subtree
        self._subtree = subtree
        # What to do with content obtained by rendering of the templates
        self.mode = mode
        # Collection of instantiated aliased entries. Dict has form
        # <aliasName> : [( <path>, <context> ), ...]
        self.instdAliases = {}

    def push(self, dirName):
        """ Appends the stack of current path tokens. """
        self._path.append( dirName )

    def pop(self, expectedName=None):
        """ Removes the last token from path tokens stack. """
        if expectedName is not None \
        and expectedName != self._path[-1]:
            raise AssertionError('Expected path token on top: "%s",'
                    ' real is "%s".'%(expectedName, self._path[-1]) )
        return self._path.pop()

    @property
    def path(self):
        """
        Returns a copy of current path tokens, without a base (root) dir.
        """
        return copy.copy(self._path)

    def current_path(self, full=False, asString=False):
        """
        An advanced method for retrieving current path stack: with or without
        root dir, whether or not to be merged into the string path.
        """
        # Get the copy of current stack
        ret = self.path
        # If `full' is requested, prepend with root
        if full:
            if type(self.root) is str:
                ret.insert( 0, self.root )
            elif type(self.root) in (tuple, list):
                ret = list(self.root) + ret
        # If string form is requested, use os.path.join() to merge a list
        if asString:
            return os.path.join(*ret)
        else:
            return tuple(ret)

    def normalized_relative_path( self, pt_ ):
        """
        Returns normalized relative path within root directory subtree.
        """
        if type(pt_) in (tuple, list):
            pt = os.path.join(pt_)
        elif type(pt_) is str:
            pt = pt_
        else:
            raise TypeError('Expected str, tuple or list.'
                    ' Got: %s'%type(pt_).__name__)
        cmPrfx = os.path.commonprefix( [pt, self.root] )
        if not cmPrfx:
            relPath = absPath
        elif cmPrfx == self.root:
            relPath = os.path.relpath( pt, start=self.root )
        else:
            raise RuntimeError('Wrong common prefix: "{prefix}".'
                    '"{locPt}" path is expected to be in a subtree'
                    ' of "{root}".'.format( prefix=cmPrfx, locPt=pt, root=self.root ))
        return relPath

    def assure_dir_exists( self, dp, pathCtx={}, alias=None ):
        """
        Recursively creates directory by given path. Absolute path is required
        to start from self.root, otherwise a warning will be printed. Relative
        path will be considered from self.root.
        """
        L = logging.getLogger(__name__)
        assert( os.path.isabs(self.root) )
        if os.path.isabs(dp):
            #assert( self.root == os.path.commonprefix([self.root, dp]) )
            if self.root != os.path.commonprefix([self.root, dp]):
                L.warning('Path %s is not relative to %s'%(dp, self.root))
                absPath = dp
                os.makedirs(dp, exist_ok=True)
                if alias:
                    self.alias_instantiated(alias, dp, pathCtx)
                return None
            else:
                relPath = self.normalized_relative_path(dp)
        else:
            relPath = dp
        # Fill path tokens list (will contain somewhat reversed form, i.e.:
        # foo/bar/zum -> [zum, bar, foo]
        ptoks = []
        pt = relPath
        while pt:
            pt, tok = os.path.split(pt)
            ptoks.append(tok)
        c = [self.root]
        for dp in reversed(ptoks):
            c.append(dp)
            jp = os.path.join(*c)
            if os.path.isdir(jp):
                continue
            os.mkdir(jp)
            cRelPath = os.path.relpath(jp, start=self.root)
            assert(cRelPath not in self._created)
            self._created[cRelPath] = pathCtx
            L.debug('Dir "%s" created.'%cRelPath )
        if alias:
            self.alias_instantiated( alias, os.path.join(self.root, relPath), pathCtx )

    def add_created_file(self, fp, pathCtx={} ):
        L = logging.getLogger(__name__)
        dirPath, _ = os.path.split( fp )
        self.assure_dir_exists( dirPath, pathCtx )
        nrp = self.normalized_relative_path(fp)
        self._created[nrp] = pathCtx
        L.debug('File "%s" created.'%nrp )

    def handle_file(self, path, globPathCtx, locPathCtx, mode=None, alias=None):
        mgr = FileHandlerContextManager( path, self, globPathCtx,
                locPathCtx, self._subtree, creationMode=mode, alias=alias)
        return mgr

    def clean_created(self):
        L = logging.getLogger(__name__)
        for p in reversed(self._created.keys()):
            try:
                if os.path.isdir(p):
                    os.rmdir(p)
                    L.debug('Dir "%s" deleted.'%p)
                elif os.path.exists(p):
                    os.remove(p)
                    L.debug('File "%s" deleted.'%p)
            except Exception as e:
                L.error('Was unable to delete entity "%s". Exception:'%p )
                L.exception(e, exc_info=True)
                # no re-raise, since we usually delete the fs within exception
                # handler and raising another exception will broke the cleaning
                # process

    def alias_instantiated(self, alias, path, context):
        L = logging.getLogger(__name__)
        if alias in self.instdAliases:
            self.instdAliases[alias].append( (path, context) )
        else:
            self.instdAliases[alias] = [(path, context)]
        L.debug( 'Alias "%s" instantiated as entry %s'%(alias, path) )

class Paths( collections.MutableMapping ):
    """
    A file structure subtree representation.
    """
    def _treat_expression(self, dirStruct, path=[]):
        ret = {}
        if dirStruct is None or not dirStruct:
            return None
        if type(dirStruct) is not dict:
            raise TypeError( 'At %s: dict expected, got %s.'%('.'.join(path)
                           , type(dirStruct)) )
        for k, value in dirStruct.items():
            nm, v = self._new_entry_at(path, k, value)
            ret[nm] = v
        return ret

    def _new_entry_at( self, path, templatedName, value ):
        L = logging.getLogger(__name__)
        m = rxFSStruct.match( templatedName )
        v = None
        if not m:
            raise BadPathTemplate( '%s at %s'%(
            templatedName, os.path.join(*path) if path else '<root>') )
        nm = m.group( 'nmTmpl' )
        if len(m.group('isFile')):
            # TODO: validate file description.
            fileRelTemplatePath = os.path.join(*(path+[nm]))
            L.debug( 'FS entry(-ies) "%s" will be considered as a file(s).'
                    , fileRelTemplatePath )
            self._files[fileRelTemplatePath] = value
            v = None
        else:
            v = self._treat_expression( value, path=(path+[nm]) )
        if 'alias' in m.groupdict().keys() and None is not m.group('alias'):
            alias = m.group('alias')
            if alias in self._aliases.keys():
                raise DulicatingAlias(alias)
            self._aliases[alias] = os.path.join(*path, nm)
        return nm, v

    def __init__(self, initObject, contextHooks={}, conditions={}):
        self._aliases = bidict.bidict({})
        self._files = {}
        self._dStruct = self._treat_expression( initObject )
        self.contextHooks = contextHooks
        self.conditions = conditions

    def __getitem__(self, key):
        return dpath.util.get( self._dStruct, key )

    def __delitem__(self):
        raise NotImplementedError()  # TODO

    def __setitem__( self, pthTuple, value ):
        L = logging.getLogger(__name__)
        path, v = None, None
        nmTemplate = None
        if type(pthTuple) is tuple:
            if 2 != len(pthTuple):
                raise KeyError(pthTuple) # p[path, name] = newEntry
            path = pthTuple[0]
            nmTemplate = pthTuple[1]
            if type(path) is str:
                if '@' == path[0]:
                    path = self._aliases[path[1:]]
                else:
                    path = os.path.normpath(path)
                path = path.split(os.sep)
            k, v = self._new_entry_at( path, nmTemplate, value )
            path += [k]
        elif type(pthTuple) is str:
            nmTemplate = pthTuple
            k, v = self._new_entry_at( [], nmTemplate, value )
            path = [k]
        else:
            raise TypeError( pthTuple )
        path = os.path.sep.join(path)
        dpath.util.new( self._dStruct, path, v )
        L.debug( 'New FS entry "%s" added at "%s".'%( nmTemplate, path ) )

    def __len__(self):
        return len(self._dStruct)

    def __iter__(self):
        return iter(self._dStruct)

    def paths_from_template(self, pt, requireComplete=True, reflexive=False, **kwargs):
        entries = []
        relevantKeys = list(filter( lambda tok: tok, [i[1] for i in Formatter().parse(pt)]))
        for argsSubset in dict_product(**{k : _rv_value(kwargs, k, requireComplete=requireComplete) for k in relevantKeys}):
            entry = pt.format_map( DictFormatWrapper( **dict(argsSubset)
                                            , requireComplete=requireComplete )
                                 )
            if reflexive:
                entry = ( entry, argsSubset )
            entries.append( entry )
        if 1 == len(entries):
            return entries[0]
        else:
            return entries


    def __call__(self, alias, requireComplete=True, reflexive=False, **kwargs):
        """
        Returns rendered template string w.r.t. to given keyword arguments.
        """
        L = logging.getLogger(__name__)
        try:
            pt = self._aliases[alias]
        except KeyError:
            # TODO: move to dedicated exception `UnknownAlias' with available
            # keys associated.
            L.error( '"%s" not in available aliases: %s'%( alias,
                ', '.join('"%s"'%str(a) for a in self._aliases.keys())
                ) )
            raise
        return self.paths_from_template( pt
                                       , requireComplete=requireComplete
                                       , reflexive=reflexive
                                       , **kwargs )
    def __str__(self):
        """
        Returns the rendered YAML text. Not actually the one that can be parsed
        and used for re-initialization (todo?), only for diagnostics.
        """
        return yaml.dump( { 'struct' : self._dStruct
                          , 'aliases' : self._aliases
                          }
            , indent=1 )

    def _generate( self, fs
                 , createdRef=None
                 , pathCtx={}
                 , leafHandler=None
                 , tContext={} ):
        """
        Generates the particular node (file or directory) recursively.
        """
        L = logging.getLogger('lamia.filesystem')
        assert(createdRef)
        for k, v in fs.items():
            createdRef.push(k)
            templatePath = createdRef.current_path(full=False, asString=True)
            fsEntryAlias = self._aliases.inv.get(templatePath, None)
            if type(v) is dict:
                self._generate( v, pathCtx=pathCtx
                    , leafHandler=leafHandler, tContext=tContext
                    , createdRef=createdRef )
                if fsEntryAlias:
                    for p, tmpContext in render_path_templates(
                                *createdRef.current_path(full=True),
                                requireComplete=True, **pathCtx ):
                        createdRef.assure_dir_exists( p, tmpContext, alias=fsEntryAlias )
            if not leafHandler:
                createdRef.pop(k)
                continue
            # 'Templated' relative path subtree token. Used as key to identify
            # particular file entity.
            # Iterate over all possible instantiations of current path template
            for p, tmpContext in render_path_templates( *createdRef.current_path(full=True)
                                                       , requireComplete=True
                                                       , **pathCtx ):
                fileDescription = self._files.get(templatePath, None)
                if fileDescription and 'conditions' in fileDescription:
                    # Some entries may have simple conditional switches that
                    # are tested against current context.
                    proceed = True
                    for cond in fileDescription['conditions']:
                        if cond.startswith('eval:'):
                            try:
                                condResult = eval( cond[5:], copy.copy(tmpContext) )
                                if not condResult:
                                    L.debug( 'Condition "{condTxt}" forbids file'
                                        ' entry "{path}" (context: {ctxTxt})'
                                        '.'.format( condTxt=cond[5:], path=p
                                                  , ctxTxt=json.dumps(tmpContext) ) )
                                proceed &= condResult
                            except:
                                L.error('..while evaluating condition "{cond}"'
                                        ' for file "{path}"'.format(cond=cond,
                                            path=p, ctxTxt=json.dumps(tmpContext) ) )
                                raise
                        else:
                            raise NotImplementedError('Condition "%s" check'
                                    ' (node "%s").'%(cond, str(p)))
                    if not proceed:
                        continue
                if p not in createdRef.visited:
                    createdRef.visited.add(p)
                else:
                    L.debug( 'Omitting visited path %s.', p )
                    continue
                # Poor-man way to determine, whether this path token
                # corresponds to file. TODO: if dir, submit mode
                if templatePath not in self._files.keys():
                    # If it is not a file, just ensure dir exists and that's
                    # it. Note, that if dir was existing before the execution,
                    # it won't be added to "created" index.
                    createdRef.assure_dir_exists( p, tmpContext, alias=fsEntryAlias )
                    continue
                if fileDescription is None:
                    # No description provided for file entry -- it's a shortcut
                    if fsEntryAlias:
                        createdRef.alias_instantiated( fsEntryAlias, p, tmpContext )
                    continue
                with createdRef.handle_file( p, tContext, tmpContext
                        , mode=None if type(fileDescription) is str else fileDescription.get('mode', None)
                        , alias=fsEntryAlias
                        ) as (context, hf):
                    try:
                        leafHandler( fileDescription, hf
                                   , path=p  # Path is used indirectly
                                   , context=context
                                   , contextHooks=self.contextHooks )
                    except:
                        L.error( 'During template-rendering handler invocation'
                                ' for node: %s', p )
                        raise
            createdRef.pop(k)

    def create_on( self, root
                 , pathCtx={}
                 , tContext={}
                 , leafHandler=None
                 , level=None
                 , createdRef=None
                 , mode=PathsDeployment.Operation.GENERATE ):
        """
        Entry point for in-dir subtree creation.
            @root is a base dir where the subtree must start
            @tContext is a file template context
            @pathCtx is a secial path-rendering context
            @leafHandler is file-template rendering object
            @level might be used to deploy only certain branch (TODO: untested)
        Internally, delegates execution to private _generate() method starting
        a recursive process of template rendering.
        Returns `createdRef' (if provided, or new instance if not) -- an
        instance of `PathsDeployment' class.

        Returns a dictionary of instantiated aliases.
        """
        L = logging.getLogger(__name__)
        if createdRef is None:
            createdRef = PathsDeployment( root, self, mode=mode )
        try:
            self._generate( self if level is None else dpath.util.get(self, level)
                    , pathCtx=pathCtx
                    , tContext=tContext
                    , leafHandler=leafHandler
                    , createdRef=createdRef )
        except Exception as e:
            nEntriesCreated = len(createdRef._created)
            L.error('An error occured during rendering subtree in "%s":'%root)
            L.exception(e, exc_info=True)
            L.error('%d entries were created prior to this error occured%s'%(
                    nEntriesCreated, ':' if nEntriesCreated else '.' ))
            for cep in createdRef._created.keys():
                L.warning( '  %s'%cep )
            if nEntriesCreated:
                if lamia.confirm.ask_for_confirm( 'Confirm deletion'
                        ' of %d newly-created or overwritten'
                        ' entries?'%nEntriesCreated, default='y' ):
                    createdRef.clean_created()
            raise
        return createdRef.instdAliases

def auto_path( p
             , fStruct=None
             , requireComplete=True
             , reflexive=False
             , **kwargs ):  # TODO: since we have kws here, **kwargs -> pathVars
    """
    `p' must be a string identifying the path in a following manner:
        - if it starts with `@' sign, the rest of the `p' content will be
        considered as an alias within `fStruct' entry. The rendered string
        corresponding to some FS subtree alias will be returned then.
        - if it contains `{}' expression, it will be considered as python-
        formatting character that is to be rendered using the context supplied
        by **kwargs.
    `fStruct' is expected to be an FS subtree description. If it is omitted,
    no `@' alias could be discovered.
    """
    L = logging.getLogger(__name__)
    try:
        m = rxFmtPat.match(p)
    except:
        L.error('While applying auto_path() to "%s"'%str(p))
        raise
    if '@' == p[0]:
        if not fStruct:
            raise ValueError('Alias given, but no filesystem subtree object'
                    ' is provided. Can not affiliate the alias.' )
        #if p[1:] not in fStruct and requireComplete:  #< XXX, not your business.
        #    raise KeyError('File structure does not define alias "%s"'%p)
        try:
            return fStruct(p[1:], requireComplete=requireComplete,
                    reflexive=reflexive, **kwargs)
        except:
            L.error('..during expansion of alias "%s".'%(p))
            raise
    elif '{' in p:
        if not fStruct:
            r = p.format_map(DictFormatWrapper( **dict(kwargs)
                        , requireComplete=requireComplete ))
            m = rxFmtPat.findall( r )
            if m and requireComplete:
                raise RuntimeError("Path template \"%s\" is incomplete within"
                        " current context: \"%s\""%( p, r ))
            if not reflexive:
                return r
            else:
                return (r, dict(kwargs))  # TODO: filter keys?
        else:
            return fStruct.paths_from_template( p, requireComplete=requireComplete
                                           , reflexive=reflexive
                                           , **kwargs )
    else:
        if not reflexive:
            return p
        else:
            return (p, {})


class FSSubtreeContext(object):
    """
    With-statement context for file structure.
    """
    def __init__( self, fsManifest
                , pathDefinitions={}, contextHooks={}, conditions={}):
        """
        Will construct file structure (if it is not yet being done).
        """
        self._fstruct = Paths(fsManifest, contextHooks=contextHooks
                , conditions=conditions)

    def __enter__(self):
        """
        Returns a Paths object, ready for use.
        """
        return self._fstruct

    def __exit__(self, excType, excValue, traceBack):
        L = logging.getLogger(__name__)
        pass  # TODO: what?

