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
Filesystem tree creating routine.
"""
#                               *** *** ***
import os, sys, logging, argparse, yaml, collections
import lamia.logging \
     , lamia.core.templates \
     , lamia.core.filesystem \
     , lamia.core.task
import lamia.routines.render
#                               *** *** ***
def _TODO_recursive_dict_update( d, u ):
    """
    Remove this function in favour of Stack() once it will support nested dict
    merging.
    """
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = _TODO_recursive_dict_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d
#                               *** *** ***
gCommonParameters = {
    'fstruct,f' : {
        'help' : "File structure template to render.",
    },
    'path_context' : {
        'help' : "Path context stack description. May be a file to be added"
            " in context stack, or alias: @fContext (for file template"
            " context), @user (for user-defined variables).",
        'action' : 'append',
        'dest' : 'path_contexts'
    },
    'path_def,P' : {
        'help' : "Path context entry definition. Similar to -D for"
            " file-template context: adds a definition within the path"
            " template rendering context. Expected to be in form"
            " <name>=<vale>.",
        'type' : lamia.core.configuration.conf_arg_expr,
        'action' : 'append',
        'dest' : 'path_definitions'
    },
    'fstruct_conf' : {
        'help' : "Section name, within fstruct doc to use."
    }
    # TODO:
    #'diff' : {
    #   'help' : 'A flag. When given, makes'
    #       ' template-rendering engine display differencies between existing'
    #        ' subtree and rendered one instead of subtree (re-)creation.'
    #        , 'action' : 'store_true'
    # }
}
gExecParameters = {
    'output_dir,o' : {
        'help' : "Base directory where subtree must be created."
    }
}
gDefaults = {
    'path_contexts' : [],
    'output_dir' : os.getcwd(),
    'path_definitions' : [],
    'fstruct_conf' : 'default',
    'contexts' : [],
    'definitions' : []
}
gEpilog="""
To make use of this procedure one need a special definition
of filesystem subtree to be deployed.
Note, that `--path-def'" entries will not take effect unless --path-ctx=@user is
specified.
"""

def parse_fstruct( fstruct, fstructConf='default', pathVariables=None ):
    """
    Returns object that typically consumed by lamia.core.filesystem.Paths
    instance constructor.
    Applies path interpolating context to given string path.
    Makes use of the path-interpolation context if appliable.
    """
    L = logging.getLogger(__name__)
    fStrObj = None
    if type(fstruct) is str:
        m = lamia.core.filesystem.rxFmtPat.match(fstruct)
        if m:
            if pathVariables is not None:
                fstruct = fstruct.format(**pathVariables)
                m = lamia.core.filesystem.rxFmtPat.match(fstruct)
                if m:
                    raise KeyError("Unable to interpolate path"
                            " string: \"%s\"."%fstruct )
            else:
                L.error('Path "%s" seems to contain formatting pattern'
                        ' but no path-formatting context being set at the'
                        ' moment.'%fstruct )
        with open(fstruct) as f:
            fStrObj = yaml.load(f)
    else:
        fStrObj = yaml.load(fstruct)
    fStrVer = fStrObj.get('version', '0.0')
    if '0.0' != fStrVer:  # TODO: finer versions control
        L.warning( "File structure version %s might be"
                " unsupported (file \"%s\")."%(fStrVer, fstruct.name \
                        if hasattr(fstruct, 'name') else fstruct) )
    fStrObj = fStrObj[fstructConf]
    if not fStrObj:
        raise RuntimeError("Empty file structure subtree description.")
    if 'extends' in fStrObj.keys():
        L.debug( ' ..loading base file structure description "%s"'%(fStrObj['extends']['path']) )
        base = parse_fstruct( fStrObj['extends']['path']
                            , fStrObj['extends'].get('conf', 'default')
                            , pathVariables=pathVariables )
        fStrObj.pop('extends')  # wipe it out since it is not an FS entry
        #base.update(fStrObj)
        fStrObj = _TODO_recursive_dict_update( base, fStrObj )
        #fStrObj = lamia.core.configuration.Stack([ base, fStrObj ])
        # TODO: use it instead of hand-written direct update, once stack
        # will support nested dictionaries
    return dict(fStrObj)
#                               *** *** ***
class DeploySubtreeTask( lamia.routines.render.RenderTemplateTask
                       , metaclass=lamia.core.task.TaskClass ):
    """
    A Lamia's task subclass performing deployment of some filesystem subtree.
    An effective subtree structure and templates have to be supplied by user
    presets.
    """
    __commonParameters=gCommonParameters
    __execParameters=gExecParameters
    __defaults=gDefaults
    __epilog=gEpilog

    class FStructContext(object):
        def __init__(self, ref):
            self._ref = ref

        def __enter__(self):
            pass
        def __exit__(self, excType, excValue, traceBack):
            pass

    def deploy_subtree( self, outputDir, fstruct
             , fstructConf='default'
             , templatesDirs=[]
             , showDiff=False ):
        """
        Single function performing rendering of the subtree. Arguments:
        @outputDir -- defines the base (target) directory where subtree has to
            be created.
        @fstruct -- the subtree description (path to YAML doc or ready object).
        @fstructConf -- defines the particular section within the @fstruct
            document
        @contexts -- additional contexts for templates rendering
        @definitions -- additional variable definitions for templates rendering
        @pathContexts -- additional contexts for path templates
        @pathDefinitions -- aditional definitions for path context
        @templatesDirs -- templates directory to consider
        Returns:
            - instance of lamia.core.templates.Templates used to render templates
              and actually deploy the subtree;
            - instance of lamia.core.filesystem.Paths describing files subtree;
            - runtime contexts stack
            - path contexts stack
            - interpolators
            - filters
        Note: probably, pointless. We usually need to perform some operations in
        between of path template-rendering and generating the actual subtree.
        """
        # TODO: confirm created subtree removal on failure
        with lamia.core.filesystem.FSSubtreeContext( parse_fstruct(fstruct, fstructConf, pathVariables=self.pStk),
                                                     onFailure=None ) as fstruct \
           , lamia.routines.render.TemplateEnvironment( [t.format(**self.pStk) for t in templatesDirs] ) as t:
            t['templates'].deploy_fs_struct( outputDir, fstruct, self.pStk, templateContext=self.rStk )

    def setup_contexts(self, contexts=[], definitions=[]
             , pathContexts=[], pathDefinitions=[]
             , templatesDirs=[]):
        self.pStk = lamia.core.configuration.compose_stack(pathContexts, pathDefinitions)
        contexts_ = [c.format(**self.pStk) if type(c) is str else c for c in contexts]
        self.rStk = lamia.core.configuration.compose_stack(contexts_, definitions)

    def _main( self, outputDir, fstruct
             , fstructConf='default'
             , contexts=[], definitions=[]
             , pathContexts=[], pathDefinitions=[]
             , templatesDirs=[]
             , showDiff=False
             , onFinish=None ):
        self.setup_contexts( contexts=contexts, definitions=definitions
                           , pathContexts=pathContexts, pathDefinitions=pathDefinitions
                           , templatesDirs=templatesDirs )
        self.deploy_subtree( outputDir, fstruct
                           , fstructConf=fstructConf
                           , templatesDirs=templatesDirs
                           , showDiff=showDiff )
#                               *** *** ***
if "__main__" == __name__:
    lamia.logging.setup()
    t = DeploySubtreeTask()
    sys.exit(t.run())

