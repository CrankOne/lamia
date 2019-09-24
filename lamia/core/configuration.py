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
Lamia module configuration processing module.

The main concept of this module is an idea of stacked configuration objects:
  - The "configuration object" represented here by `Configuration' class is
basically a classic Python dictionary with `dpath'-based element querying.
  - The "stacking" of configuration objects means that they may override each
other, in a way like native Python `dict.update()' method does, except for
retaining the previous state. One can "push" configuration object in the top
of the stack causing new object to shadow present entries of the previous one
(so, e.g., the {'foo':2} on top of {'foo':1} will shadow 'foo' and
myStack['foo'] will return `2').
  If the top entry has no particular entry, it still might be found below on
the stack unless it was explicitly deleted on some level.

Planned (TODO/not yet fully implemented):
The `Stack' class also offers some command-line adopted DSL for managing
collections within `Configuration' object. Examples:
    foo=1       # define a scalar named "foo" with value `1'
    ~bar        # un-define entry "bar"
    spam.=1     # define/apend a list named "spam" with value 1
    egg=a:12    # define/append a dictionary "egg" with entry "a":`12'
    spam~=foo:  # remove element "foo" from list "spam"
    ...etc.
"""

import yaml, dpath.util, copy, collections, logging, sys \
     , configparser, json, yaml, re, argparse, inspect
import lamia.core.interpolation
from io import IOBase
from urllib.parse import urlparse
from functools import reduce

DPSP = '.'
gSupportedShebangs = set({'// JSON', '# YAML', '; INI'})

# Generic validation expression for command-line parameter overriding
gRxConfExpr=re.compile(r'^~?[A-Za-z_][\w.-]+(?:[+.-~]?=.+)?$')
# For collection-modification actions, will yield either <name:value> pair (for
# dicts), or only <value> (for lists).
gRxCollectionOperation=re.compile(r'^(?:(?P<name>[^:]+)(?<!\\):)?(?P<value>.+)?$')
# Semantic parsers for command-line parameter overriding
gRxConfExprSemantics = {
        'decl-scalar' : re.compile( r'^(?P<name>[A-Za-z][\w.-]+)=(?P<value>(?:\\,|[^,\n])+)$' ),
              'undef' : re.compile( r'^~(?P<name>[A-Za-z][\w.-]+)$' ),
          'cltAppend' : re.compile( r'^(?P<name>[A-Za-z_][\w.-]+)\.=(?P<value>.+)?$' ),
             'cltPop' : re.compile( r'^(?P<name>[A-Za-z_][\w.-]+)~=(?P<value>.+)?$' )
    }

class StackTagError(RuntimeError):
    pass

def parse_context_stream( argsFPath ):
    """
    Accepts file path and parses it into the python dictionary. The following
    extensions are allowed:
        - .json, .js, .JSON, .JS -- for JSON file format
        - .yaml, .YAML -- for YAML file format
        - .ini, .INI, .cfg, .erb -- for INI config file format
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
    elif len(argsFPath) > 4 and ('.ini' == argsFPath[-4:] or \
                                 '.cfg' == argsFPath[-4:] or \
                                 '.erb' == argsFPath[-4:]):
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
                    cfg = parse_context_stream( pst.path )
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
        elif initObject is None:
            cfg = {}
        else:
            raise TypeError("Unexpected type for Configuration object"
                    " initialization: %s."%type(initObject))
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
    # static method:
    def _obj_to_cfg(self, obj):
        if type(obj) is not Configuration:
            return Configuration(obj)
        else:
            return obj
        return obj

    def __init__( self, initObj=[] ):
        """
        Constructs configuration stack. The initializing object may be given
        either as starting Configuration initializer object (or instance) or
        as a list of objects, in which case each of them will be considered
        as an instance of configuration or its initializer object.
        It is also possible to assemble a tagget stack by passing the pairs
        (two-element tuples) within the list in form (<cfg-init-obj>, <tag>).
        """
        self._stack = []
        if type(initObj) is list:
            for c in initObj:
                if type(c) is tuple:
                    c, tag = c
                    self.push(self._obj_to_cfg(c), tag=tag)
                else:
                    self.push(self._obj_to_cfg(c))
        elif initObj:
            self.push(self._obj_to_cfg(initObj))
        else:
            raise TypeError('Unexpected type/empty dict given for'
                    ' configuration stack initialization: %s.'%type(initObj) )

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
        if (tag is not None \
            and self._stack[-1][0] != tag) \
        or (tag is None \
            and self._stack[-1][0] is not None):
            raise StackTagError( 'Configuration stack tag mismatch;'
                ' has: %s, tried: %s.'%( self._stack[-1][0], tag) )
        self._stack.pop()

    def argparse_override(self, overrideExpr):
        """
        Utilizes expressions validated by conf_arg_expr().
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
        elif 'cltAppend' == expr['do']:
            pName, pVal = expr['name'], expr['value']
            vm = gRxCollectionOperation.match(expr['value'])
            cn, cv = vm.groupdict()['name'], vm.groupdict()['value']
            if pName not in self:
                L.debug( 'Adding new collection "%s".'%pName )
            raise NotImplementedError('TODO: collections operations')
        elif 'cltPop' == expr['do']:
            pName, pVal = expr['name'], expr['value']
            if pName not in self:
                L.debug( 'Won\'t remove "%s" from collection "%s" since'
                        ' it doesn\'t exist.'%(pName, pVal) )
            raise NotImplementedError('TODO: collections operations')
        else:
            raise NotImplementedError('TODO: support for "%s"'
                    ' conf-overriding action.')

    def stacked(self, *args, **kwargs):
        """
        Returns a `StackConfs' instance to be used as `with'-context mgr.
        """
        return StackConfs( *args, __base=self, **kwargs )

    def apply(self, callee, argsListName=None ):
        """
        Invokes given function with values taken from this config stack,
        matching to signature.
        """
        L = logging.getLogger(__name__)
        s = inspect.signature(callee)
        args=[]
        kwargs={}
        ctx = copy.copy(dict(self))
        for pn, p in s.parameters.items():
            if inspect.Parameter.POSITIONAL_ONLY == p.kind:
                raise NotImplementedError("Positional only args aren't supported.")
                #if pn in ctx:  # TODO no name for positional only?
                #    args.append( ctx.pop(pn) )
                #elif p.default != inspect.Parameter.empty:
                #    args.append( p.default )
                #else:
                #    raise TypeError('No value for "%s" in call of %s.'%(
                #        pn, str(f)))
            elif inspect.Parameter.POSITIONAL_OR_KEYWORD == p.kind:
                if pn in ctx:
                    args.append( ctx.pop(pn) )
                elif p.default != inspect.Parameter.empty:
                    args.append( p.default )
                else:
                    raise TypeError('No value for "%s" in call of %s.'%(
                        pn, str(callee)))
            elif inspect.Parameter.VAR_POSITIONAL == p.kind:
                args += ctx.pop(argsListName) if argsListName in ctx else [[]]
            elif inspect.Parameter.KEYWORD_ONLY == p.kind:
                if pn in ctx:
                    kwargs[pn] = ctx.pop(pn)
                elif p.default != inspect.Parameter.empty:
                    kwargs[pn] = p.default
                else:
                    raise TypeError('No value given and no default value is'
                            ' defined for "%s" in call of %s.'%(
                                pn, str(callee)))
            elif inspect.Parameter.VAR_KEYWORD == p.kind:
                kwargs.update(ctx)
        L.debug('Applying conf stack: %s, %s'%(str(args), str(kwargs)))
        return callee(*args, **kwargs)

def compose_stack( ctx=[], defs=[] ):
    """
    A common pattern of applying the configuration stack is to specify the list
    of config files and user overriding definitions within the command line.
    This function helps to apply them.
    """
    if not ctx: ctx = []
    if not defs: defs = []
    stk = Stack( ctx )
    for d in defs:
        stk.argparse_override(d)
    return stk


class StackConfs(object):
    """
    With-statement context for temporary configuration stacks.
    """
    def __init__(self, *args, definitions=[], __base=None, **kwargs):
        L = logging.getLogger(__name__)
        if __base is None:
            self._stk = Stack()
        elif type(__base) is Stack:
            self._stk = __base
        else:
            self._stk = Stack(__base)
        self._entries = list(args)
        self._defs = copy.copy(definitions)
        self._entries.append(dict(kwargs))
        L.debug("Entering temporary stack context; entries: %s"%str(self._entries))

    def __enter__(self):
        for n, c in enumerate(self._entries):
            self._stk.push( c, tag='%s-%s'%(str(id(self)), str(n)) )
        for d in self._defs:
            self._stk.argparse_override(c)
        return self._stk

    def __exit__(self, excType, excValue, traceBack):
        for d in self._defs:
            self._stk.pop()
        for n, c in reversed(list(enumerate(self._entries))):
            self._stk.pop( tag='%s-%s'%(str(id(self)), str(n)) )

