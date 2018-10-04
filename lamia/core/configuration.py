# -*- coding: utf-8 -*-
import yaml, dpath.util, copy, collections, logging, sys \
     , configparser, json, yaml, re, argparse
import lamia.core.interpolation
from io import IOBase
from urllib.parse import urlparse
from functools import reduce

"""
Lamia module configuration files processing module.
"""

DPSP = '.'
gSupportedShebangs = set({'// JSON', '# YAML', '; INI'})

gRxConfExpr=re.compile(r'^~?[A-Za-z_][\w.-]+(?:[+-]?=.+)?$')
gRxConfExprSemantics = {
        'decl-scalar' : re.compile( r'^(?P<name>[A-Za-z][\w.-]+)=(?P<value>(?:\\,|[^,\n])+)$' ),
        'undef'  : re.compile( r'^~(?P<name>[A-Za-z][\w.-]+)$' )
        # TODO: 'modify-list', 'declare-list', etc.
    }

class StackTagError(RuntimeError):
    pass

def parse_context_stream( argsFPath ):
    """
    Accepts file path and parses it into the python dictionary. The following
    extensions are allowed:
        - .json, .js, .JSON, .JS -- for JSON file format
        - .yaml, .YAML -- for YAML file format
        - .ini, .INI, .cfg -- for INI config file format
    If '-' specified as file path, will try to read from STDIN. The first line
    given will be considered as a shebang describing the input format, and
    following will be interpreted:
        '// JSON' -- for JSON data (other comments aren't supported within the
            file)
        '# YAML' -- for YAML data
        '; INI' -- for INI config.
    If format is not recognized, raises RunTimeError().
    """
    L = logging.getLogger(__name__)
    cfg = None
    if type(argsFPath) is not str:
        raise ValueError('String expected, got: %s'%type(argsFPath))
    elif '-' == argsFPath:
        fmt = ''
        while '' == fmt:
            fmt = sys.stdin.readline()[:-1]
        if fmt not in gSupportedShebangs:
            raise RuntimeError('The "%s" string is not a format-description.'
                    ' Expected are: "%s".'%(fmt, '", "'.join(gSupportedShebangs)) )
        argsText = sys.stdin.read()
        L.debug( 'Argument input of format "%s" of length has been %d slurped.'%(fmt, len(argsText)) )
        if '; INI' == fmt:
            iniCfg = configparser.ConfigParser()
            iniCfg.read_string(argsText)
            cfg = dict(iniCfg._sections)
        elif '// JSON' == fmt:
            cfg = dict(json.loads(argsText))
        elif '# YAML' == fmt:
            cfg = yaml.load(argsText)
        else:
            # Impossible stub:
            raise AssertionError('Format recognized, but not being parsed.')
    elif len(argsFPath) > 4 and ('.ini' == argsFPath[-4:] or '.cfg' == argsFPath[-4:]):
        iniCfg = configparser.ConfigParser()
        iniCfg.read(argsFPath)
        cfg = dict(iniCfg._sections)
    elif len(argsFPath) > 5 and '.yaml' == argsFPath[-5:]:
        with open(argsFPath, 'r') as f:
            cfg = dict(yaml.load(f))
    elif len(argsFPath) > 5 and '.json' == argsFPath[-5:]:
        with open(argsFPath) as f:
            cfg = dict(json.load(f))
    else:
        pass  # do nothing, leave cfg being `None'
    if cfg is None:
        raise RuntimeError( 'Unrecognized context input format.'
            ' File path: "%s".'%argsFPath )
    return cfg

class ConfigInterpolator(object):
    """
    Config interpolator allows one to refer to the entities that are already
    present in the configuration structure using path with indexes delimeted
    by comma.
    """
    def __init__(self, dct):
        self.dct = dct

    def __call__(self, strval):
        if not strval:
            raise RuntimeError('Got empty config path.')
        elif strval[0] in '@-+':
            raise NotImplementedError("Cfg ops aren't yet supported.")  # TODO
        return dpath.util.get(self.dct, strval, separator=DPSP)

def conf_arg_expr(expr):
    """
    argparse's custom validator for config-manipulation expressions.
    """
    # NOTE useful pattern: ^(?P<name>[^=]+)(?<!\\)=(?P<val>.+)$
    m = gRxConfExpr.match(expr)
    if not m:
        raise argparse.ArgumentTypeError( "'{}' is not a valid lamia.config"
                " expression.".format(expr))
    return expr


class Configuration(collections.MutableMapping):
    """
    Configuration representated as mutable mapping with shortened element
    subscription implemented by `dpath' module.

    TODO: impose support for the dpath's globes.
    """
    def __init__( self
                , initObject={}
                , interpolators=None
                , selfInterpolationTag=None
                , switches={} ):
        """
        One can construct the configuration either from the string value, or
        from file by the given path.
        """
        L = logging.getLogger(__name__)
        if not interpolators:
            self._interpolators = lamia.core.interpolation.Processor()
        else:
            self._interpolators = interpolators
        cfg = {}
        if type(initObject) is str:
            if '\n' not in initObject:
                pst = urlparse(initObject)
                if '' == pst.scheme \
                or 'file' == pst.scheme:
                    # TODO: support not only the YAML
                    cfg = parse_context_stream( pst.path )
                # ... elif (more schemes to be supported: http/ftp/etc)
                else:
                    raise NotImplementedError( "URI Scheme \"%s\" is not yet supported."%pst.scheme )
            else:
                cfg = yaml.load(initObject)
        elif isinstance(initObject, IOBase):
            cfg = yaml.load( initObject )
        elif type(initObject) is dict:
            cfg = copy.deepcopy(initObject)
        elif type(initObject) is None:
            initObject = {}
        elif isinstance(initObject, Configuration):
            cfg = copy.deepcopy(initObject._store)
        for k, v in switches.items():
            try:
                cfg[v[1]] = copy.deepcopy(cfg[k][v[0]])
            except KeyError:
                L.error( 'Available keys: %s.'%(', '.join(cfg.keys())) )
            del(cfg[k])
        if selfInterpolationTag:
            self._interpolators[selfInterpolationTag] = ConfigInterpolator(cfg)
        else:
            self._interpolators['value'] = ConfigInterpolator(cfg)
        interpolated = self._interpolators( cfg )
        self._store = dict( interpolated )

    def __deepcopy__(self, memo):
        return Configuration(self)

    def __contains__(self, k):
        if DPSP in k:
            try:
                dpath.util.get( self._store, k, separator=DPSP )
            except KeyError:
                return False
            return True
        else:
            return k in self._store.keys()

    def __getitem__(self, pth):
        ret = None
        if DPSP in pth:
            ret = dpath.util.get( self._store, pth, separator=DPSP )
        else:
            ret = dict.__getitem__(self._store, pth)
        return self._interpolators(ret)

    def __setitem__(self, pth, val):
        if DPSP in pth:
            dpath.util.new( self._store, pth, val, separator=DPSP )
        else:
            self._store[pth] = val

    def __delitem__(self, key):
        del self._store[self.__keytransform__(key)]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def set_existing(self, pth, key):
        if DPSP in pth:
            nChanged = dpath.util.set( self._store, pth, val, separator=DPSP )
            if nChanged:
                return nChanged
        raise KeyError( pth )

class Stack(collections.MutableMapping):
    """
    This class orginizes Configuration instances in a stack, supporting
    entries retrieval. The latest (being on top of the stack) Configuration
    instances overrides the below ones in terms of presence.
    Caveat: to override the entry which is present in the former configuration
    in terms of deletion, use the special Stack.Deleted object.
    """
    def __init__( self ):
        self._stack = []

    class _Deleted(object):
        """
        A special tombstone class marking entries being deleted from cfg.
        Has to be never exposed outside the Stack class.
        """
        pass

    def __getitem__(self, pth):
        """
        Will pass through the configuration stack, from top to the bottom,
        trying to retrieve the requested value. Will raise KeyError exception
        if entry was explicitly deleted or does not exist at any level.
        """
        if not self._stack:
            raise RuntimeError( "Configuration stack is empty." )
        for tag, e in reversed( self._stack ):
            try:
                val = e[pth]
            except KeyError:
                continue
            if type(val) is Stack._Deleted:
                raise KeyError( 'The "%s" entry was explicitly deleted.'%pth )
            return val
        raise KeyError( pth )

    def __setitem__(self, path, val):
        """
        Sets the entry within top Configuration instance on the stack.
        """
        if not self._stack:
            self._stack = [ ( None, Configuration({})) ]
        self._stack[-1][1][path] = val

    def __delitem__(self, path):
        """
        Will set the certain item within topmost Configuration instance to
        _Deleted instance as a tombstone. If no such entry found, it will be
        marked as a deleted anyway.
        """
        self._stack[-1][1][path] = Stack._Deleted()

    def __contains__(self, k):
        for tag, c in reversed( self._stack ):
            if k in c.keys():
                try:
                    val = c[k]
                except( lamia.core.interpolation.InterpolationTypeError ) as e:
                    if e.type_ is Stack._Deleted:
                        return False
                return not isinstance(val, Stack._Deleted)
        return False

    def __iter__(self):
        keysPassed = set({})
        for tag, c in reversed(self._stack):
            for k, v in c.items():
                if k not in keysPassed:
                    keysPassed.add(k)
                else:
                    continue
                if not isinstance(v, Stack._Deleted) :
                    yield k

    def __len__(self):
        uniqKeys = {}  # (key, exists)
        for tag, c in reversed(self._stack):
            for k, v in c.items():
                if k not in uniqKeys.keys():
                    uniqKeys[k] = isinstance( v, Stack._Deleted )
        return reduce( lambda c, v: int(c) if v else int(c) + 1, uniqKeys.values(), 0 )

    def push( self, c, tag=None ):
        """
        Only dict/Configuration instances are allowed. Otherwise, type error
        will be raised.
        """
        # Copy original, even if it is already a configuration
        c = Configuration( c )
        self._stack.append( (tag, c) )

    def pop( self, tag=None ):
        if tag is not None \
        and self._stack[-1][0] is not None \
        and self._stack[-1][0] != tag:
            raise StackTagError( 'Has: %s, tried: %s.'%( self._stack[-1][0], tag) )
        self._stack.pop()

    def argparse_override(self, overrideExpr):
        """
        Utilizes expressions validated by ConfigArgType.
        """
        L = logging.getLogger(__name__)
        expr = {}
        for action, rx in gRxConfExprSemantics.items():
            m = rx.match(overrideExpr)
            if not m: continue
            expr = m.groupdict()
            expr['do'] = action
            break
        if not expr:
            raise ValueError("Unable to interpret config-modifying expression"
                    " \"%s\"."%overrideExpr )
        if 'decl-scalar' == expr['do']:
            self[expr['name']] = expr['value']
            L.debug( 'Entry "%s" := "%s" defined in conf stack.'%(
                                        expr['name'], expr['value'] ) )
        elif 'undef' == expr['do']:
            del(self[expr['name']])
            L.debug( 'Entry "%s" deleted from stack.'%( expr['name'] ) )
        else:
            # TODO ...
            raise NotImplementedError('TODO: support for "%s"'
                    ' conf-overriding action.')

