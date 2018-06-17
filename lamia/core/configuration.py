# -*- coding: utf-8 -*-
import yaml, dpath.util, copy, collections, logging
import lamia.core.interpolation
from io import IOBase
from urllib.parse import urlparse
from functools import reduce

"""
Lamia module configuration files processing module.
"""

DPSP = '.'

class StackTagError(RuntimeError):
    pass

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
        L = logging.getLogger('lamia.configuration')
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
                    with open( pst.path ) as f:
                        cfg = yaml.load( f )
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
        for k, v in switches.items():
            try:
                cfg[v[1]] = copy.copy(cfg[k][v[0]])
            except KeyError:
                L.error( 'Available keys: %s.'%(', '.join(cfg.keys())) )
            del(cfg[k])
        if selfInterpolationTag:
            self._interpolators[selfInterpolationTag] = ConfigInterpolator(cfg)
        else:
            self._interpolators['value'] = ConfigInterpolator(cfg)
        interpolated = self._interpolators( cfg )
        self._store = dict( interpolated )

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
                raise KeyError( 'The "%s" entry was explicitly deleted'
                        ' from configuration.' )
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
            if k in c:
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
                if k not in keysPassed \
                and not isinstance(v, Stack._Deleted) :
                    keysPassed.add(k)
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
        if not isinstance( c, Configuration ):
            c = Configuration(c)
        self._stack.append( (tag, c) )

    def pop( self, tag=None ):
        if tag is not None \
        and self._stack[-1][0] is not None \
        and self._stack[-1][0] != tag:
            raise StackTagError( 'Has: %s, tried: %s.'%( self._stack[-1][0], tag) )
        self._stack.pop()

