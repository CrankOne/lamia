# -*- coding: utf-8 -*-
"""
Lamia helper class for reentrant tasks definition.
A task class describes the working process in terms of high-level reentrant
components. Typical staging:
  1) Set up a command-line argument parser, using reentrant blocks of
foreign modules. Set a default values, that may vary from one task to another.
  2) Load an filesystem subtree description. It is usually an artifact.
  3) Pre-form a preliminary path template-rendering context, apply it to the
FS-subtree description, to obtain caching paths.
  4) Fetch/form preliminary caches, fully define the template-rendering and
path-rendering contexts.
  5) Deploy subtree.
A utilizing modules as well as some descendant classes introducing some common
functionality might be found in the `lamia.routines' module. The former are
usually relevant to some implications for the staging, therefore involving
evaluation of corresponding routine.
"""
import argparse, logging, types
import inflection
import lamia.logging

def _argparse_par(s):
    """
    A helper function splitting a given token into shortcut and long name.
    Input/output examples:
        "a"         -> ("a", None)
        "a,aleph"   -> ("a", "aleph")
        "aleph"     -> (None, "aleph")
    Used within the Task class to define argparse arguments from static
    descriptions.
    """
    name, shortcut = None, None
    if ',' in s:
        a, b = s.split(',')
        if 1 == len(a):
            shortcut, name = a, b
        elif 1 == len(b):
            shortcut, name = b, a
        else:
            raise RuntimeError( "Unable to determine the name/shortcut"
                    " correspondance for \"%s\"."%s )
    elif 1 == len(s):
        shortcut = s
    else:
        name = s
    if shortcut:
        shortcut = '-' + shortcut
    if name:
        name = '--' + inflection.dasherize(name)
    return shortcut, name

class Task(object):
    """
    The `Task' abstraction states an implication that all runnable procedure
    may be invoked directly, by specifying a set of the input arguments that
    may be provided by set of command line arguments.
    To achieve this, we assume:
        1. The set of arguments may be splitted into two sub-sets:
            1.a) A reentrant arguments that potentially might be supplied by
            some external code (e.g., task may be included within bigger
            encompassing task).
            1.b) A set of arguments specific for the current execution.
        2. The set of default arguments may vary between tasks.
    At this level of abstraction we only make assumptions above, no
    implications about actual `run()' method is made.
    """
    def add_parameters(self, ps):
        L = logging.getLogger()
        for pName, pDescr in ps.items():
            if '@' != pName[0]:
                arg = list(filter(lambda x: x, _argparse_par(pName)))
                self.argParser.add_argument( *arg, **pDescr )
                L.debug( '"%s" named command-line arg added'%(', '.join(arg)) )
            else:
                self.argParser.add_argument( pName[1:], **pDescr )
                L.debug('Added a positional argument.')

    def __init__(self):
        """
        Initializes the instance's argument parser.
        """
        lamia.logging.setup()
        L = logging.getLogger()
        self._p = argparse.ArgumentParser() # TODO: description=self.__doc__, epilog=self.__epilog )
        for pN in ['common_parameters', 'exec_parameters']:
            ps = getattr(self, 'get_%s'%pN)()
            L.debug( 'Task base class: got list of length %d for "%s".'%(
                len(ps), pN ) )
            ps = lamia.core.configuration.Stack( ps )
            L.debug( 'Top entities in stack: %s.'%(', '.join( '"%s"'%k for k in ps.keys() )) )
            self.add_parameters( ps )
        #self.add_parameters( lamia.core.configuration.Stack(self.get_common_parameters()) )
        #self.add_parameters( lamia.core.configuration.Stack(self.get_exec_parameters()) )
        self._p.set_defaults( **lamia.core.configuration.Stack(self.get_defaults()) )

    @property
    def argParser(self):
        return self._p

    def run(self):
        L = logging.getLogger()
        if not (hasattr(self, '_main') and self._main):
            L.error( 'Entry point is not defined by task instance.' )
            return 1
        argsDct = { inflection.camelize(k, uppercase_first_letter=False) : v \
                for k, v in vars(self.argParser.parse_args()).items() }
        # TODO: check compatibility?
        L.debug('Run args: %s'%argsDct)
        return self._main(**argsDct)

def cumulative_class_property_getter(prop):
    """
    Decorator returning a walk-through getter collecting the
    __<className>_<propertyName> class properties within the inheritance chain.
    Comes with implication that `get_<propertyName>' getters in parent classes
    are also cumulative (brings property accumulated within their parents).
    """
    varName = inflection.camelize(prop, uppercase_first_letter=False)
    getterName = 'get_%s'%prop
    def _recurse_getter(cls):
        st = []
        for bCls in cls.__bases__:
            # Invoke eponymous getter for all direct bases, if appliable,
            # in order.
            if hasattr(bCls, getterName):
                st += getattr(bCls, 'get_%s'%prop)()
        attrName = '_%s__%s'%( cls.__name__, varName)
        # Append the list with own, of appliable
        if hasattr( cls, attrName ):
            st += [(getattr( cls, attrName ), cls.__name__)]
        return st
    return classmethod(_recurse_getter)

class TaskClass(type):
    """
    A metaclass assembling class from few sources.
    """
    def __new__(cls, clsname, superclasses, attributedict):
        L = logging.getLogger(__name__)
        L.debug("New task class derived: `%s'; superclasses: %s; dict: {%s}."%(
            clsname,
            ', '.join(list(map(lambda x: x.__name__, superclasses))),
            ', '.join(['"%s"'%k for k in attributedict.keys()]) )
            )
        # Check that new class is derived from 
        hasTaskBase = False
        for supCls in superclasses:
            if issubclass(supCls, Task):
                hasTaskBase = True
                break
        if not hasTaskBase:
            raise AssertionError( "Class `%s' is not derived from `%s'."%(
                cls.__name__, Task.__name__) )
        # Inject getters
        for pN in ['common_parameters']:
            attributedict['get_%s'%pN] = cumulative_class_property_getter( pN )
        attributedict['get_exec_parameters'] = classmethod( lambda cls :
                getattr(cls, '_%s__execParameters'%cls.__name__) )
        attributedict['get_defaults'] = classmethod( lambda cls :
                getattr(cls, '_%s__defaults'%cls.__name__) )
        # Produce class object
        return super().__new__(cls, clsname, superclasses, attributedict)

def module_task( className
               , entryPoint
               , dependencies=[Task]
               , m={}, additionalAttribs={}
               ):
    """
    Automatically assembles module definitions into task class.
    To instantiate a task, one may either utilize this class with a module of
    specific form, or subclass it. This class represents the first case.
    Usage example:
        if "__main__" == __name__:
            t = lamia.core.task.module_task( 'MyTask', globals(), my_main )
        sys.exit(t.run())
    Will construct a new class to eval the `my_main' routine as an
    entry point with parameters defined in first-level variables listed in
    constructor doc.
        The `m' argument is a module's `globals()' dict in which we assume
    presence of `gCommonParameters', `gExecParameters', `gDefaults' and
    `gEpilog' variables. The module's __doc__ string will be taken as
    `prog' documentation string.
    The `dependencies' must be filled with modules this task depends on.
    Their common parameters will be injected into set of current
    parameters.
    """
    # Form inheritance chain.
    superclasses = []
    for dep in dependencies:
        #if type(dep) is types.ModuleType:
        #    # This is a flat module, not a class
        #    self.add_parameters( getattr(dep, 'gCommonParameters', {}) )
        #    L.debug('"%s" module\'s parameters appended.'%(dep.__name__))
        if isinstance(dep, type):
            superclasses.append( dep )  # is a class, to become a parent
    # Form attributes dict
    def _loc_key(clsName, k):
        if 'g' != k[0]:
            return k
        return '_%s__%s%s'%(clsName, k[1].lower(), k[2:])
    def _loc_main(self):
        super().__init
    attributes = { _loc_key(className, k) : m.get(k, None) for k in [
        'gCommonParameters'
        , 'gExecParameters'
        , 'gDefaults'
        , 'gEpilog'
        , '__doc__' ] }
    # Append attributes dict with run() method and ctr:
    attributes['_main'] = lambda self, *args, **kwargs: entryPoint(*args, **kwargs)
    #attributes['__init__'] = lambda self: .__init__()  # TODO: ?
    return TaskClass( className
                    , tuple(superclasses)
                    , attributes)

