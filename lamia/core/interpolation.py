# -*- coding: utf-8 -*-
import re, logging, yaml
import lamia.core.configuration

"""
String interpolation within the config variables.

Following syntax is offered within string values:
    $(<GROUP-ID>:<IDENTIFIER>)
where GROUP-ID defines the method of getting values named by IDENTIFIER.

The main idea is to enhance the ability of config files to interact with
execution environment. Possible GROUP-ID for example is ENV retreiving the
strings from environment variables.

Interpolation methods may be defined and added dynamically into the special
processor entity.
"""

rxsPattern = r'\$\((?P<name>[a-zA-Z_][a-zA-Z1-9_]*):(?P<identifier>(?:(?:(?:\\[($)])|[^($)])*))\)'
maxSubst = 255

def yaml_include(loader, node):
    with open(node.value) as f:
        return yaml.load(f)

yaml.add_constructor("!include", yaml_include)

class InterpolationTypeError(TypeError):
    def __init__( self, t ):
        self.type_ = t
        super().__init__( "Unexpected type \"%s\" is given to string"
                    " interpolation callable."%str(t) )

class Processor(dict):
    """
    String interpolation callable.
    """
    def __init__(self):
        """
        Trivial ctr.
        """
        self.rx = re.compile(rxsPattern)

    def __call__(self, v):
        """
        Performs interpolation for collections: dicts, lists, sets or forwards
        single string interpolation to interpolate_str() method.
        """
        L = logging.getLogger('lamia.interpolation')
        if v is None:
            return None
        t = type(v)
        if t is float \
        or t is int \
        or t is bool \
        or v is None:
            ret = v
        elif t is str:
            return self.interpolate_str(v)
        elif t is dict or t is lamia.core.configuration.Configuration:
            ret = {}
            for k, v in v.items():
                try:
                    ret[k] = self(v)
                except Exception:
                    L.error( 'Within "%s":'%k )
                    raise
            return ret
        elif t is list:
            ret = list(map(self, v))
        elif t is set:
            ret = set(map(self, v))
        # elif ...
        else:
            #raise InterpolationTypeError( t )
            return v
        return ret

    def interpolate_str(self, v):
        """
        Performs substitution within given string.
        """
        # We do the while True loop here instead of finditer() or whatever
        # because of the fact the string substitution will usually change
        # the string positions, so each time the search has to be re-run.
        iv = v
        substCount = 0
        while True and substCount != maxSubst:
            m = self.rx.search( v )
            if not m:
                break
            nm, idnt = m.group('name'), m.group('identifier')
            if nm not in self.keys():
                raise KeyError("Unknown parameter interpolation \"%s\"."%nm)
            ret = self[nm](idnt)
            if ret is None:
                # If you've got this error, but intended returning an empty
                # interpolation, consider using of empty string instead.
                raise RuntimeError('Parameter interpolation \"%s\" returned' \
                        ' None.'%nm)
            elif type(ret) is str:
                # We treat strings intepolation as a classic strings
                # substitution.
                #return re.sub(self.rx, ret, v)
                v = v[:m.start()] + ret + v[m.end():]
            elif type(ret) in (int, float):
                # Only full match is supported.
                if m.start() != 0 or m.end() != len(iv):
                    raise RuntimeError('Extra symbols on for'
                            ' int/float substitution in "%s".'%iv)
                return ret
            elif type(ret) is list:
                # Only full match is supported.
                if m.start() != 0 or m.end() != len(iv):
                    raise RuntimeError('Extra symbols on for'
                            ' list substitution in "%s".'%iv)
                return ret
            elif type(ret) is dict:
                # Only full match is supported.
                if m.start() != 0 or m.end() != len(iv):
                    raise RuntimeError('Extra symbols on for'
                            ' dict substitution in "%s".'%iv)
                return ret
            elif type(ret) is set:
                # Only full match is supported.
                if m.start() != 0 or m.end() != len(iv):
                    raise RuntimeError('Extra symbols on for'
                            ' set substitution in "%s".'%iv)
                return ret
            # TODO: elif type(ret) is ConfDifferencies ...
            else:
                raise RuntimeError('Interpolation of type "%s" is not'
                        ' supported.'%str(type(ret)) )
            substCount += 1
        if substCount == maxSubst:
            raise RecursionError('Recursive or too complex substitution'
                    ' detected for expression "%s".'%iv )
        return v

class DictInterpolator(dict):
    """
    A very simple interpolating wrapper for python dictionaries.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.__getitem__(*args, **kwargs)

