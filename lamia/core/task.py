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
import sys, argparse, logging, types, functools
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
    return shortcut, name

class Task(object):
    """
    The `Task' abstraction implies that all runnable procedures may be invoked
    directly (i.e. without any additional setup), by specifying a set of the
    input arguments that may be provided by set of command line arguments.
    To achieve this, we assume:
        1. The set of arguments may be splitted into two sub-sets:
            1.a) A reentrant arguments that potentially might be supplied by
            some external code (e.g., task may be included within bigger
            encompassing task).
            1.b) A set of arguments specific for the current execution.
        2. The set of default arguments may vary between tasks.
    At this level of abstraction we only make assumptions above, no
    implications about actual `run()' method is made.
    Note: one may provide the `__epilog' class variable to define the
    argparse's "epilog" message (printed at the end after the usage info in
    help/usage reference).
    """
    def add_parameters(self, ps):
        L = logging.getLogger()
        if self._userDefaults is None:
            self._userDefaults = {}
        usedUserDfts = set(self._userDefaults.keys())
        self._argNames = set()
        for pName, pDescr in ps.items():
            if '@' != pName[0]:
                shortcut, name = _argparse_par(pName) #list(filter(lambda x: x, _argparse_par(pName)))
                self._argNames.add( name if name else shortcut )
                assert( name or shortcut )
                if name and name in self._userDefaults:
                    pDescr['default'] = self._userDefaults[name]
                    L.debug( '{name} default is set/overriden by users {value}'.format(
                        name=name if name else shortcut, value=self._userDefaults[name] ) )
                    usedUserDfts.add(name)
                if shortcut: shortcut = '-' + inflection.dasherize(shortcut)
                if name: name = '--' + inflection.dasherize(name)
                nms = list(filter(lambda x: x, [shortcut, name]))
                self.argParser.add_argument( *nms
                                           , **pDescr )
                L.debug( '"%s" named command-line arg added'%(', '.join(nms)) )
            else:
                self.argParser.add_argument( pName[1:], **pDescr )
                L.debug('Added a positional argument.')
        return usedUserDfts

    def _instantiate_arg_parser(self):
        L = logging.getLogger(__name__)
        self._p = argparse.ArgumentParser( self.__class__.__doc__,
                epilog=getattr( self.__class__
                              , '_%s__epilog'%self.__class__.__name__, None ) )
        usedUserDfts = set()
        for pN in ['common_parameters', 'exec_parameters']:
            ps = getattr(self, 'get_%s'%pN)()
            L.debug( 'Task base class: got list of length %d for "%s".'%(
                len(ps), pN ) )
            ps = lamia.core.configuration.Stack( ps if ps else [] )
            L.debug( 'Top entities in stack: %s.'%(', '.join( '"%s"'%k for k in ps.keys() )) )
            usedUserDfts |= self.add_parameters( ps )
        unusedUserDfts = set(self._userDefaults.keys()) - usedUserDfts
        if unusedUserDfts:
            L.warning( 'Unused user defaults: %s'%(', '.join(unusedUserDfts)) )
        #self.add_parameters( lamia.core.configuration.Stack(self.get_common_parameters()) )
        #self.add_parameters( lamia.core.configuration.Stack(self.get_exec_parameters()) )
        dfts = self.get_defaults()
        dfts = lamia.core.configuration.Stack( dfts if dfts else [] )
        self._p.set_defaults( **dfts )
        L.debug( 'Default values set for %s.'%(', '.join(
            ['%s="%s"'%(k, str(v)) for k, v in dfts.items()])) )

    def __init__(self):
        pass

    @property
    def argParser(self):
        if not hasattr(self, '_p'):
            self._instantiate_arg_parser()
        return self._p

    def run(self, args=sys.argv[1:], overrideDefaults=None):
        """
        Runs task. If user config (`overrideDefaults') is given (not being set
        to None), it will override default parameters from command line
        arguments (but if command-line parameters are set to non-default values
        they take precedence). Priority (bigger override lower):
            1. default parameters set by routines themselves
            2. parameters from user config (`overrideDefaults')
            3. parameters supplied by command line
        In case of lists, the values will be stacked up.
        """
        L = logging.getLogger()
        if not (hasattr(self, '_main') and self._main):
            L.error( 'Entry point is not defined by task instance.' )
            return 1
        if overrideDefaults and hasattr(self, '_p'):
            # Considered as an erroneous architect.
            raise RuntimeError( "`overrideDefaults' kwarg is provided but"
                    " arg parser already instantiated." )
        self._userDefaults = overrideDefaults
        argsDct = { inflection.camelize(k, uppercase_first_letter=False) : v \
                for k, v in vars(self.argParser.parse_args(args)).items() }
        L.debug('Run args: %s'%argsDct)
        self.taskCfg = lamia.core.configuration.Stack(argsDct)
        # For batch-operating task(s), instantiate a monitoring API
        if isinstance(self, lamia.backend.interface.BatchTask):
            self.setup_monitoring(          self.taskCfg.get('monitoringAddr', None)
                                 ,     tags=self.taskCfg.get('monitoringTag', None)
                                 ,  comment=self.taskCfg.get('monitoringComment', None)
                                 , username=self.taskCfg.get('monitoringUser', None)
                                 ,    email=self.taskCfg.get('monitoringEmail', None)
                                 )
        return self.taskCfg.apply(self._main)

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
                st += getattr(bCls, getterName)()
        attrName = '_%s__%s'%( cls.__name__, varName)
        # Append the list with own, of appliable
        if hasattr( cls, attrName ):
            st += [(getattr( cls, attrName ), cls.__name__)]
        return st
    return classmethod(_recurse_getter)

def cumulative_class_property_keys_getter(prop):
    """
    Similar to cumulative_class_property_getter() getter-constructor, but
    returns a flattened set of keys. Relies on the method created by
    cumulative_class_property_getter().
    """
    def _recurse_getter(cls):
        cpgName = 'get_%s'%prop
        assert(hasattr(cls, cpgName))  # no cumulative_class_property_getter()!
        # list of dicts:
        pl = [d[0] for d in getattr(cls, cpgName)()]
        # list of lists:
        pl = [[k if 'dest' not in v else v['dest'] for k, v in d.items()] for d in pl]
        # set of strings:
        pl = functools.reduce( lambda acc, x: acc + x, pl )
        def _f(nm):
            shortcut, name = _argparse_par(nm)
            return name if name else shortcut
        return set([inflection.camelize(_f(nm), uppercase_first_letter=False) \
                    for nm in pl])
    return classmethod(_recurse_getter)

class TaskClass(type):
    """
    A metaclass assembling class from few sources. Expects the following
    class properties to be defined:
        `__commonParameters' -- a dictionary describing parameters, common for
    any subclass inheriting this task class
        `__execParameters' -- a dictionary describing parameters necessary only
    for the standalone run of this task.
        `__defaults' -- a dictionary of default values for argument.
        `__cumulativeDefaults' -- whether or not to consider `__defaults' as
    a cumulative dict, i.e. to propagate ones from base classes to child. Note,
    that if direct base classes have their own bases, it won't be automatically
    propagated unles this property is not set for them as well.
        `__depends' -- a list of deendencies to be evaluated prior to task
    being defined. May contain entries of following types:
            - class reference (imported); will be evaluated unconditionally
            - a pair of function and class reference; will be evaluated if
            function receiving the result of evaluation is true. Function
            receives arguments ...
    """
    def __new__(cls, clsname, superclasses, attributedict):
        L = logging.getLogger(__name__)
        # Check that new class is derived from 
        hasTaskBase = False
        for supCls in superclasses:
            if issubclass(supCls, Task):
                hasTaskBase = True
                break
        if not hasTaskBase:
            raise AssertionError( "Class `%s' is not derived from `%s'."%(
                cls.__name__, Task.__name__) )
        L.debug('Defining new class "%s" with attribute dict keys: %s.'%(
            clsname, ' '.join( '"%s"'%k for k in attributedict.keys() )))
        # Inject getters
        cumulativeGetters = ['common_parameters']
        if not attributedict.pop('_%s__cumulativeDefaults'%clsname, False):
            attributedict['get_defaults'] = classmethod( lambda cls_ :
                    [getattr(cls_, '_%s__defaults'%cls_.__name__, {})] )
        else:
            cumulativeGetters.append('defaults')
            L.debug('Default values are set to be cumulative'
                    ' for class "%s".'%(clsname))
        for pN in cumulativeGetters:
            attributedict['get_%s'%pN] = cumulative_class_property_getter( pN )
            attributedict['get_%s_names'%pN] \
                    = cumulative_class_property_keys_getter(pN)
        attributedict['get_exec_parameters'] = classmethod( lambda cls_ :
                [getattr(cls_, '_%s__execParameters'%cls_.__name__, {})] )
        # Produce class object
        L.debug("New task class derived: `%s'; superclasses: %s; dict: {%s}."%(
            clsname,
            ', '.join(list(map(lambda x: x.__name__, superclasses))),
            ', '.join(['"%s"'%k for k in attributedict.keys()]) )
            )
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
    def _invoke_main(self):
        return self.taskCfg.apply(entryPoint)
    attributes['_main'] = _invoke_main
    #attributes['__init__'] = lambda self: .__init__()  # TODO: ?
    return TaskClass( className
                    , tuple(superclasses)
                    , attributes)

