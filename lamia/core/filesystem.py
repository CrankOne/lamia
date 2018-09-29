import os, sys, errno, collections, re, dpath, yaml, itertools, logging, copy \
     , glob, contextlib, argparse
import lamia.core.interpolation, lamia.core.configuration
from string import Formatter

"""
Various auxilliary filesystem routines, coming in hand for lamia procedures.
"""

rxsFSStruct = r'^(?P<isFile>!?)(?P<nmTmpl>[^@/\n]+)(?:@(?P<alias>[_\-\w]+))?$'
rxFSStruct = re.compile(rxsFSStruct)

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
    Order is arbitrary.
    """
    L = logging.getLogger(__name__)
    scalars = {}
    sequences = {}
    for k, v in kwargs.items():
        if _is_seq(v):
            sequences[k] = v
        else:
            scalars[k] = v
    keys = sequences.keys()
    vals = sequences.values()
    for instance in itertools.product(*vals):
        dct = dict(zip(keys, instance))
        dct.update(scalars)
        yield dct

def render_path_templates(*args, requireComplete=True, **kwargs):
    """
    Renders the path according to given list of templated string and formatting
    arguments.
    Note, that in case of redundant kwargs, it will produce duplicating paths,
    so user code must get rid of them.
    """
    L = logging.getLogger(__name__)
    L.debug('Generating path templates product on: %s; %s.'%(
        ', '.join(args), str(kwargs) ))
    s = os.path.join(*args)
    keys = filter( lambda tok: tok, [i[1] for i in Formatter().parse(s)] )
    for skwargs in dict_product(**{ k : kwargs[k] for k in keys }):
        yield s.format_map(DictFormatWrapper( dict(skwargs)
                                            , requireComplete=requireComplete )) \
            , skwargs

def check_dir( path, mode=None ):
    """
    Ensures that directory exists and, optionally, has proper access rights.
    If dir doesn't exist, it will be created either with 0o777, or with given
    mode permissions.
    If mode is None, no mode check is performed.
    """
    try:
        os.makedirs( path )
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

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
        super().__init__(*args, **kwargs)

    def __missing__(self, key):
        if self.requireComplete:
            raise IncompleteContext( key )
        else:
            return '{%s}'%key

class Paths( collections.MutableMapping ):
    def _treat_expression(self, dirStruct, path=[]):
        ret = {}
        if dirStruct is None or not dirStruct:
            return None
        if type(dirStruct) is not dict:
            raise TypeError('At %s: dict expected, got %s.'%('.'.join(path)
                , type(dirStruct)) )
        for k, value in dirStruct.items():
            nm, v = self._new_entry_at(path, k, value)
            ret[nm] = v
        return ret

    def _new_entry_at( self, path, templatedName, value ):
        L = logging.getLogger('lamia.filesystem')
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

    def __init__(self, initObject):
        self._aliases = {}
        self._files = {}
        self._visited = None
        self._dStruct = self._treat_expression( initObject )

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

    def __call__(self, alias, requireComplete=True, **kwargs):
        """
        Returns rendered template string w.r.t. to given keyword arguments.
        """
        pt = self._aliases[alias]
        return pt.format_map(DictFormatWrapper( dict(kwargs)
                                              , requireComplete=requireComplete))

    def __str__(self):
        """
        Returns the rendered YAML text. Not actually the one that can be parsed
        and used for re-initialization (todo?), only for diagnostics.
        """
        return yaml.dump( { 'struct' : self._dStruct
                          , 'aliases' : self._aliases
                          }
            , indent=1 )

    def _generate( self, root, path, fs
                 , pathCtx={}
                 , leafHandler=None
                 , tContext={} ):
        """
        Generates the particular node (file or directory) recursively.
        """
        L = logging.getLogger('lamia.filesystem')
        for k, v in fs.items():
            np = path + [k]
            if type(v) is dict:
                self._generate( root, np, v, pathCtx=pathCtx
                    , leafHandler=leafHandler, tContext=tContext )
            if not leafHandler:
                continue
            for p, pathContext in render_path_templates( *([root] + np)
                                                       , requireComplete=True
                                                       , **pathCtx ):
                templatePath = os.path.join(*np)
                if p not in self._visited:
                    self._visited.add(p)
                else:
                    L.debug( 'Omitting visited path %s.', p )
                    continue
                if templatePath not in self._files.keys():
                    check_dir( p )
                    continue
                dirPath, filename = os.path.split(p)
                check_dir( dirPath )
                if dirPath not in self._visited:
                    check_dir( dirPath )
                    self._visited.add(dirPath)
                # Update the pathCtx with pathContext here
                if isinstance( pathCtx, lamia.core.configuration.Stack ):
                    pathCtx.push( pathContext
                                , tag='recursive-path-subst' )
                elif type( pathCtx ) is dict:
                    pathCtx = copy.deepcopy( pathContext )
                else:
                    raise TypeError( type(pathCtx) )
                # Take care of the entites that are not presented in current
                # context within the runtime stack (explicitly mark them as
                # deleted) since path context shall contain ONLY the keys
                # consumed within current path.
                for pathKey in pathCtx.keys():
                    if pathKey not in pathContext.keys():
                        del pathCtx[pathKey]
                # Apply the appropriate handler to generate the leaf node.
                try:
                    L.debug( 'handling the "%s"', p )
                    # The pathCtx will be available within the
                    # template as well.
                    context = copy.deepcopy( tContext )
                    if 'p' in context.keys():
                        L.warning( 'The "p" is already in'
                                ' template\'s context. Preserving it.' )
                    else:
                        context['p'] = pathCtx
                    if 'paths' in context.keys():
                        L.warning( 'The "paths" is already in'
                                ' template\'s context. Preserving it.' )
                    else:
                        context['paths'] = self
                    leafHandler( self._files[templatePath]
                               , path=p
                               , context=context )
                except:
                    L.error( 'During handler invokation for node: %s'
                           , p )
                    raise
                finally:
                    if isinstance( pathCtx, lamia.core.configuration.Stack ):
                        pathCtx.pop( tag='recursive-path-subst' )

    def create_on( self, root
                 , pathCtx={}, tContext={}, leafHandler=None ):
        self._visited = set()
        self._generate( root, [], self
                , pathCtx=pathCtx
                , tContext=tContext
                , leafHandler=leafHandler )
        self._visited = None

