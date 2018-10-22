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
Uses Lamia engine with various presets to render a template.
"""
import re, os, sys, dpath, json
import argparse, logging, datetime, subprocess
import lamia.core.interpolation \
     , lamia.core.templates \
     , lamia.core.configuration \
     , lamia.core.task
import lamia.logging
#                               *** *** ***
rxTmplRExpr=re.compile(r'^(?P<name>[^=]+)(?<!\\)=(?P<val>.+)$')
#                               *** *** ***
gCommonParameters = {
    'template_dir,T' : {
        'help' : "Directory where templates have to be discovered.",
        'action' : 'append',
        'dest' : 'templates_dirs'
    },
    'context' : {
        'help' : "A YAML/INI/JSON file describing context for rendering the"
            " template(s).",
        'action' : 'append',
        'dest' : 'contexts'
    },
    'define_var,D' : {
        'help' : 'A template-context substitution.',
        'action' : 'append',
        'dest' : 'definitions',
        'type' : lamia.core.configuration.conf_arg_expr
    }
}

gExecParameters = {
    '@template' : {
        'help' : "The template(s) to render. The `-' will"
            " be considered as stdin descriptor and the stdin input will be"
            " exected.",
        'nargs' : '+'
    }
}

gDefaults = {
    'templates_dirs' : [],
    'contexts' : [],
    'definitions' : []
}

gEpilog = """Note, that options `-T', `-D', `-c,--context' may be specified few
times. They will be applied in order.
NOTE: if stdin/stdout (`-') entities specified few times, they will be expected
to appear in order:
1) Arguments, prefixed with INI/JSON/YAML in the first line in order of they
were given in cmd-line.
2) Template, in order of they were given in cmd-line. Then the output will be
generated.
Consider that using same stdin few times, however being a bad style.
"""
#                               *** *** ***
class RenderTemplateTask( lamia.core.task.Task
                        , metaclass=lamia.core.task.TaskClass ):
    """
    A template-rendering task class abstraction.
    """
    __commonParameters = gCommonParameters
    __execParameters = gExecParameters
    __defaults = gDefaults
    __epilog = gEpilog

    def setup_rendering( self
                       , templatesDirs
                       , contexts
                       , definitions=[]):
        """
        Based on given input parameters, will set up properties:
            self.rStk -- runtime stack
            self.tli -- Lamia template-loading interpolators dictionary
            self.fltr -- Lamia template filters object
            self.t -- lamia Templates instance (accessible by the self.t)
        """
        self.rStk = lamia.core.configuration.compose_stack(contexts, definitions)
        self.tli = lamia.core.interpolation.Processor()
        #self.tli['REAL_PATH'] = os.path.realpath
        #self.tli['PATH_VAR'] = lambda nm: str(self.pStk[nm])
        self.fltrs = { 'abspath'    : lamia.core.templates.AbsPathFilter(os.getcwd())
                     , 'commonpath' : lamia.core.templates.CommonPathFilter(os.getcwd()) }
        self.t = lamia.core.templates.Templates( templatesDirs
                                      , loaderInterpolators=self.tli
                                      , additionalFilters=self.fltrs
                                      , extensions=['jinja2.ext.do'] )

    def _main( self
             , template=None
             , templatesDirs=[]
             , contexts=[]
             , definitions=[] ):
        """
        Entry point for single template rendering with standard contexts.
        Sets up contexts, creates template-rendering object instance and applies it
        against given templates (or reads template from stdin).
        """
        L = logging.getLogger(__name__)
        assert(template)
        self.setup_rendering(templatesDirs, contexts, definitions)
        #
        for tmplName in template:
            if '-' == tmplName:
                # Input from stdin requested:
                tmplTxt = sys.stdin.read()
                if not tmplTxt or len(tmplTxt) is None:
                    L.error('Skipping template string of length zero got from stdin.')
                L.debug( 'template input of length %d slurped.'%len(tmplTxt) )
                txtRendered = lamia.core.templates.render_string( tmplTxt, self.fltrs, **self.rStk )
                L.debug( 'Rendering template <string of length %d> -> stdout.'%(len(tmplTxt)) )
                sys.stdout.write( txtRendered )
                continue
            m = rxTmplRExpr.match(tmplName)
            if m:
                tmplName, tmplOutFile = m.groupdict()['name'], m.groupdict()['val']
            else:
                # The given template name doesn't match to pattern
                # <template>=<outfile>, so consider given argument as just a
                # template name and try to render it as is.
                tmplOutFile = '-'
            L.debug( 'Rendering template "%s" -> "%s".'%(tmplName, tmplOutFile) )
            txtRendered = self.t( tmplName, **self.rStk )
            if '-' == tmplOutFile:
                sys.stdout.write( txtRendered )
            else:
                with open(tmplOutFile, 'w') as f:
                    f.write(txtRendered)
        return 0
#                               *** *** ***
if "__main__" == __name__:
    lamia.logging.setup()
    t = RenderTemplateTask()
    sys.exit(t.run())

