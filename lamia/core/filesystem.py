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
     , glob, contextlib, argparse
import lamia.core.interpolation, lamia.core.configuration
from string import Formatter

rxsFSStruct = r'^(?P<isFile>!?)(?P<nmTmpl>[^@/\n]+)(?:@(?P<alias>[_\-\w]+))?$'
rxFSStruct = re.compile(rxsFSStruct)
rxFmtPat = re.compile(r'\{[^}\s]+\}')

# By default, templates may refer to current Path object instance by this
# key.
DFT_PATH_KEY='__p'

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
    for instance in itertools.product(*vals):
        dct = dict(zip(keys, instance))
        dct.update(scalars)
        if not callables:
            yield dct
        else:
            callableAppendix = {}
            for ck, c in callables.items():
                callableAppendix[k] = c(dct)
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
    keys = list(filter( lambda tok: tok, [i[1] for i in Formatter().parse(s)]))
    try:
        for skwargs in dict_product(**{
                k : _rv_value(kwargs, k, requireComplete=requireComplete) \
                        for k in keys }):
            dfw = DictFormatWrapper( **dict(skwargs)
                                   , requireComplete=requireComplete )
            try:
                np = s.format_map(dfw)
                yield np, skwargs
            except:
                L.error( 'During yielding product result on sub-keyword args:'
                    ' {%s}, turned in formatting dict with keys {%s}.'%(
                        ', '.join([ '"%s"'%skwa for skwa in skwargs ])
                        , ', '.join(['"%s"'%k for k in dfw.keys()]) ) )
                raise
    except:
        L.error( 'During yielding the path %s on set of keys: {%s}.'%(
            s, ', '.join(['"%s"'%k for k in keys])) )
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

class PathsDeployment(object):
    """
    Stores information about filesystem entries being visited, created,
    updated, etc. Used to inspect the ongoing process and to clean-up the
    entities just being created in case of something goes wrong.
    """
    def __init__(self, root ):
        assert(type(root) is str)
        # list of path (as strings) being visited
        self.visited = set()
        # filesystem subtree dict-like tree of entities being created
        self._created = collections.OrderedDict()
        # current list of path tokens, stacked during recursive traversal
        self._path = []
        # base directory for deployment (filesystem subtree prefix)
        self.root = os.path.realpath( root )

    def push(self, dirName):
        self._path.append( dirName )

    def pop(self, expectedName=None):
        if expectedName is not None \
        and expectedName != self._path[-1]:
            raise AssertionError('Expected path token on top: "%s",'
                    ' real is "%s".'%(expectedName, self._path[-1]) )
        return self._path.pop()

    @property
    def path(self):
        return copy.copy(self._path)

    def current_path(self, full=False, asString=False):
        """
        Returns current path stack.
        """
        ret = self.path
        if full:
            if type(self.root) is str:
                ret.insert( 0, self.root )
            elif type(self.root) in (tuple, list):
                ret = list(self.root) + ret
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

    def assure_dir_exists( self, dp, pathCtx ):
        if check_dir( dp ):
            dpath.util.new( self._created, dp, {} )  # TODO: pathCtx

    def add_created_file(self, fp, pathCtx ):
        dpath.util.new( self._created, self.normalized_relative_path(fp), {} )  # TODO: pathCtx

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
            if value is None:
                raise BadFileDescription( '%s at %s'%(templatedName, os.path.join(*path)) )
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

    def __init__(self, initObject, pKey=DFT_PATH_KEY, contextHooks={}):
        """
        Templates may refer to volatile path-rendering context entities with
        name given by `pKey'.
        """
        self._aliases = {}
        self._files = {}
        self._pKey = pKey
        self._dStruct = self._treat_expression( initObject )
        self.contextHooks = contextHooks

    def __getitem__(self, key):
        return dpath.util.get( self._dStruct, key )

    def __delitem__(self):
        raise NotImplementedError()  # TODO

    def __setitem__( self, pthTuple, value ):
        L = logging.getLogger('lamia.filesystem')
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
            if type(v) is dict:
                self._generate( v, pathCtx=pathCtx
                    , leafHandler=leafHandler, tContext=tContext
                    , createdRef=createdRef )
            if not leafHandler:
                continue
            # 'Templated' relative path subtree token. Used as key to identify
            # particular file entity.
            templatePath = createdRef.current_path(full=False, asString=True)
            # Iterate over all possible instantiations of current path template
            for p, tmpContext in render_path_templates( *createdRef.current_path(full=True)
                                                       , requireComplete=True
                                                       , **pathCtx ):
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
                    createdRef.assure_dir_exists( p, tmpContext )
                    continue
                dirPath, filename = os.path.split(p)
                if dirPath not in createdRef.visited:
                    createdRef.assure_dir_exists( dirPath, tmpContext )
                    createdRef.visited.add(dirPath)
                # Update the pathCtx with tmpContext here
                if isinstance( pathCtx, lamia.core.configuration.Stack ):
                    pathCtx.push( tmpContext
                                , tag='recursive-path-subst' )
                elif type( pathCtx ) is dict:
                    pathCtx = copy.deepcopy( tmpContext )
                else:
                    raise TypeError( type(pathCtx) )
                # Take care of the entites that are not presented in current
                # context within the runtime stack (explicitly mark them as
                # deleted) since path context shall contain ONLY the keys
                # consumed within current path.
                for pathKey in pathCtx.keys():
                    if pathKey not in tmpContext.keys():
                        del pathCtx[pathKey]
                # Apply the appropriate handler to generate the leaf node.
                try:
                    L.debug( 'handling the "%s"', p )
                    context = copy.deepcopy( tContext )
                    if self._pKey in context.keys():
                        L.warning( 'The "%s" is already in'
                            ' template\'s context. Preserving it.'%self._pKey )
                    else:
                        context[self._pKey] = pathCtx
                    if 'paths' in context.keys():
                        L.warning( 'The "paths" is already in'
                                ' template\'s context. Preserving it.' )
                    else:
                        context['paths'] = self
                    # TODO: finer control over the file creation -- delegate it
                    # to `createdRef'
                    leafHandler( self._files[templatePath], path=p
                               , context=context, contextHooks=self.contextHooks )
                    createdRef.add_created_file(p, tmpContext)
                except:
                    L.error( 'During template-rendering handler invocation'
                            ' for node: %s', p )
                    raise
                finally:
                    if isinstance( pathCtx, lamia.core.configuration.Stack ):
                        pathCtx.pop( tag='recursive-path-subst' )
            createdRef.pop(k)

    def create_on( self, root
                 , pathCtx={}
                 , tContext={}
                 , leafHandler=None
                 , level=None
                 , createdRef=None ):
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
        """
        if createdRef is None:
            createdRef = PathsDeployment( root )
        self._generate( self if level is None else dpath.util.get(self, level)
                , pathCtx=pathCtx
                , tContext=tContext
                , leafHandler=leafHandler
                , createdRef=createdRef )
        #tr = asciitree.LeftAligned()
        #print(tr(createdRef._created))
        return createdRef

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
    def __init__( self, fsManifest, pathDefinitions={}
                , onFailure=None, pKey=DFT_PATH_KEY, contextHooks={}):
        """
        Will construct file structure (if it is not yet being done).
        """
        self._fstruct = Paths(fsManifest, pKey=pKey, contextHooks=contextHooks)
        self._onFailure = onFailure

    def __enter__(self):
        """
        Returns a Paths object, ready for use.
        """
        return self._fstruct

    def __exit__(self, excType, excValue, traceBack):
        L = logging.getLogger(__name__)
        if excType:
            if self._onFailure:
                self._onFailure( self._fstruct, excType, excValue, traceBack )
            else:
                L.error( 'onFailure-handler is not set for filesystem subtree'
                        ' context manager.' )

