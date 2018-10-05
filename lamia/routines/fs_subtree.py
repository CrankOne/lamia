# -*- coding: utf-8 -*-
"""
Filesystem tree creating routine.
"""
import os, sys, logging, argparse, yaml
import lamia.logging, lamia.core.templates, lamia.core.task
import lamia.routines.render
#                               *** *** ***
class Deployment(lamia.core.task.Task):
    """
    A Lamia's task subclass performing deployment of some filesystem subtree.
    An effective subtree structure and templates have to be supplied by user
    presets.
    """
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    def run(self):
        super().run()
#                               *** *** ***
gCommonParameters = {
    'fstruct,f' : {
        'help' : "File structure template to render."
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
    'fstruct_conf' : 'default'
}

gEpilog="""
To make use of this procedure one need a special definition
of filesystem subtree to be deployed.
Note, that `--path-def'" entries will not take effect unless --path-ctx=@user is
specified.
"""
#                               *** *** ***
def deploy_fstruct( outputDir=None
                  , fstruct=None
                  , fstructConf='default'
                  , contexts=[], definitions=[]
                  , pathContexts=[], pathDefinitions=[]
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
    assert(outputDir)
    assert(fstruct)
    #
    if type(fstruct) is str:
        with open(fstruct) as f:
            fstruct = lamia.core.filesystem.Paths( yaml.load(f)[fstructConf] )
    rStk = lamia.core.configuration.compose_stack(contexts, definitions)
    tli = lamia.core.interpolation.Processor()
    tli['PATH'] = os.path.realpath
    fltrs = { 'abspath'    : lamia.core.templates.AbsPathFilter(os.getcwd())
            , 'commonpath' : lamia.core.templates.CommonPathFilter(os.getcwd()) }
    pStk = lamia.core.configuration.compose_stack(pathContexts, pathDefinitions)
    t = lamia.core.templates.Templates( templatesDirs
                                      , loaderInterpolators=tli
                                      , additionalFilters=fltrs
                                      , extensions=['jinja2.ext.do'] )
    t.deploy_fs_struct( outputDir, fstruct, pStk
                      , templateContext=rStk )
    return t, fstruct, rStk, pStk, ints, fltrs
#                               *** *** ***
if "__main__" == __name__:
    t = lamia.task.Task( globals()
                       , name=sys.modules[__name__]
                       , entryPoint=deploy_fstruct
                       , dependencies=[na58.routines.render] )
    sys.exit(t.run())

