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

import yaml, os, fnmatch, logging, datetime, copy
import jinja2 as j2
import jinja2.lexer, jinja2.ext
import lamia.core.configuration as LC
import lamia.core.filesystem as FS
from enum import Enum

# Template files extension.
TEMPLT_FLS_PAT = '*.yaml'
# Default access mode for files created.
DFTFMOD = 0o664

class BadAbsolutePath(ValueError):
    """
    Given absolute path does not contain the necessary base.
    """
    pass

class CommonPathFilter(object):
    """
    Jinja2 path-sanitizing filter that ensures that given path is absolute and
    is related to some common base. If it is relative, the absolute path will
    be computed and substituted. If it is absolute and does not relates to the
    base, exception will be thrown.
    """
    def __init__(self, base):
        self._base = os.path.normpath(base)

    def __call__(self, relPath):
        if os.path.isabs( relPath ):
            if os.path.commonprefix(self._base, relPath) == self._base:
                return os.path.normpath(relPath)
            else:
                raise BadAbsolutePath( relPath )
        return os.path.join( self._base, relPath )

class AbsPathFilter(object):
    """
    Jinja2 path-sanitizing filter that ensures that given path is absolute. If
    it is relative, assumes that it is relative to some common base and returns
    absolutized path.
    """
    def __init__(self, base):
        self._base = os.path.normpath(base)

    def __call__(self, relPath):
        if os.path.isabs( relPath ):
            return os.path.normpath(relPath)
        return os.path.join( self._base, relPath )

class Loader(j2.BaseLoader):
    """
    A custom template loader class for Lamia. Its templates are the YAML files
    and have to be treated correspondingly.

    The `template' YAML document has to contain at least the `template' string
    within, have the .yaml extension and be the valid YAML file.
    """
    def _load_yaml_object(self, fPath):
        """
        Internal function performing loading the document. Called by
        _discover_templates() and has to return (content, modtime) tuple.
        """
        L = logging.getLogger('lamia.templates')
        with open(fPath) as f:
            try:
                content = yaml.load(f)
                mt = os.path.getmtime(fPath)
            except Exception as e:
                L.exception(e)
                L.error('... while processing "%s". File ignored.'%fPath)
            else:
                if type(content) is not dict or 'template' not in content.keys():
                    L.warning( 'No "template" field found in %s. Ignored.'%fPath )
                    return None
                else:
                    L.debug( 'template %s loaded.'%fPath )
                    return content, mt
        return None

    def _discover_templates(self, templatesRoot, interpolators=None):
        """
        Searches for valid Lamia's template documents by given path and loads
        them into returned dict.
        """
        L = logging.getLogger('lamia.templates')
        ret = {}
        for root, dirnames, filenames in os.walk(templatesRoot):
            for filename in fnmatch.filter(filenames, TEMPLT_FLS_PAT):
                fPath = os.path.join(root, filename)
                yObj, mt = self._load_yaml_object( fPath )
                if yObj is not None:
                    tName = os.path.splitext(os.path.relpath( fPath, templatesRoot ))[0]
                    L.debug('Loaded template "%s" from'
                            ' file "%s" (%s)'%( tName, fPath
                                              , datetime.datetime.fromtimestamp(mt)))
                    ret[tName] = ( LC.Configuration(yObj, interpolators=interpolators)
                                 , fPath, mt)
        return ret

    def __init__(self, templateDirs, interpolators=None):
        """
        Ctr has to be initialized with root templates folder. All the template
        documents will be parsed and loaded immediately.
        """
        L = logging.getLogger('lamia.templates')
        if type(templateDirs) is str:
            self.templates = self._discover_templates( templateDirs
                                                 , interpolators=interpolators )
        elif type(templateDirs) is list:
            self.templates = {}
            for tD in templateDirs:
                self.templates.update( self._discover_templates( tD
                                     , interpolators=interpolators ) )
        else:
            raise TypeError( type(templateDirs) )
        L.info( '%d templates collected.'%(len(self.templates)) )

    def get_source(self, environment, template):
        """
        Overriden method from Jinja2 API. Returning tuple and arguments are
        standartized.
        """
        L = logging.getLogger('lamia.templates')
        if template not in self.templates.keys():
            raise j2.TemplateNotFound(template)
        # TODO: no need for realoading, actally. May be implement in future.
        yObj, pth, mt = self.templates[template]
        # TODO: seems like stacktrace uses this path to get the line content.
        # Has to somehow trick it in order to display real template line instead
        # of yaml's.
        # We may get the line number information from YAML file by utilizing
        # this approach: https://stackoverflow.com/questions/13319067/parsing-yaml-return-with-line-number
        # And further prepend the template string with commented {#-#} lines to
        # get the proper line numbering.
        return yObj['template'], pth, lambda: True

class Operation(Enum):
    GENERATE = 1
    EXTRACT_DIFFS = 2

class _RecursiveTemplatesHandler(object):
    def __init__( self, renderers={}, mode=Operation.GENERATE ):
        self.renderers = renderers
        self.mode = mode

    def __call__( self, template, path=None, context={} ):
        L = logging.getLogger('lamia.templates')
        L.debug( 'Rendering of %s.'%path )
        rTxt = None
        if type(template) is str:
            if '@' == template:
                # A special case for files paths that do not correspond to any
                # file created by subtree-creating procedure, but rather being
                # injected into subtree for further usage in user code.
                return
            rTxt = self.renderers['default'](template, **context)
        elif type(template) is dict:
            if 'id' in template.keys():
                rTxt = self.renderers[template.get('class', 'default')]( template['id']
                        , **context)
            elif 'class' in template.keys():
                if template['class'] is not None:
                    rTxt = self.renderers[template.get('class', 'default')]( template
                        , **context)
                else:
                    return
                    # ^^^ The case of class: None has to remain possible, and
                    # means ``just keep the file as it is''.
        else:
            raise TypeError( 'Expected either a string identifying template'
                    ' or a dictionary with "class" field, not an instance of'
                    ' "%s".'%(type(template)) )
        if Operation.GENERATE == self.mode:
            with open(path, 'w') as f:
                f.write(rTxt)
            mode = template.get('mode', DFTFMOD) if type(template) is dict else DFTFMOD
            os.chmod(path, mode)
        else:
            # TODO: at least EXTRACT_DIFFS may come in hand soon
            raise NotImplementedError( "Operation %s of"
                    " Lamia template engine."%self.mode )

class PlainTextRenderer(object):
    """
    Silly plain text template renderer.
    """
    def __init__(self, dct):
        self.dct = dct

    def __call__(self, tID, **unused):
        return self.dct[tID]

class Templates(object):
    """
    Default templates renderer.
    """
    def __init__( self, templatesDirs
                , loaderInterpolators=None
                , mode=Operation.GENERATE
                , additionalFilters={}
                , extensions=[] ):
        self.mode = mode
        # Require target dir to be accessible and actually a dir (or a symlink
        # to dir)
        for d in templatesDirs:
            if type(d) is not str or not os.path.isdir(d):
                raise ValueError( 'Not a directory: "%s".'%str(d) )
        # Set template interpolators, create loader (loads templates instantly,
        # create template-rendering environment)
        self.loaderInterpolators = loaderInterpolators
        self.loader = Loader(templatesDirs, interpolators=self.loaderInterpolators)
        self.env = j2.Environment( loader=self.loader
                                 , undefined=j2.StrictUndefined
                                 , extensions=extensions )
        for k, fltr in additionalFilters.items():
            self.env.filters[k] = fltr

    def __call__(self, templateName, **kwargs):
        """
        Renders template identified by templateName, making the
        substitutions acc. to kwargs.
        """
        #cfg = self.loaderInterpolators['CFG'].dct
        #alb = self.loaderInterpolators['ALBK'].dct
        t = self.env.get_template(templateName)
        # TODO: put valiadation checks here?
        return t.render( ctx=self.loaderInterpolators, **kwargs)

    def __getitem__(self, k):
        return self.loaderInterpolators[k]

    def deploy_fs_struct( self, root, fs, pathTemplateArgs
                        , renderers={}
                        , templateContext={} ):
        """
        Performs deployment of filesystem structure subtree according to fiven
        subtree description and template-rendering context.
        @root -- base dir for subtree deployment
        @fs -- subtree manifest (description) document
        @pathTemplateArgs -- template context for path rendering
        @renderers -- supplementary template renderers
        @templateContext -- a dict-like context object for template rendering
        (usually a lamia.core.configuration.Stack object).
        """
        L = logging.getLogger('lamia.templates')
        if not issubclass( type(fs), FS.Paths ):
            raise TypeError( "lamia.core.filesystem.Paths subclass instance"
                    " expected as interpolator, got %s."%type(fs) )
        if 'default' in renderers.keys():
            # Puzzling message. Means that hereafter we use foreign template
            # renderer instead of current instance when it is reffered to
            # "default".
            L.warning( 'Template renderer "default" will be overriden when'
                    ' deploying FS structure.' )
        renderers['default'] = self
        fs.create_on( root
                , pathCtx=pathTemplateArgs
                , tContext=copy.deepcopy(templateContext)
                , leafHandler=_RecursiveTemplatesHandler(renderers=renderers) )

def render_string( strTmpl, _additionalFilters={}, _extensions=[], **kwargs ):
    """
    Renders a string as a anonymous template with existing context.
    """
    loader = kwargs.get('_loader', j2.BaseLoader)
    try:
        e = j2.Environment( loader=loader
                          , extensions=_extensions
                          , undefined=j2.StrictUndefined )
        for k, fltr in _additionalFilters.items():
            e.filters[k] = fltr
        t = e.from_string(strTmpl)
        return t.render(**kwargs)
    except:
        L = logging.getLogger('lamia.templates')
        L.error( 'during rendering of string """%s""" with context %s',
                strTmpl, str(dict(kwargs)))
        raise

class ContextStack(jinja2.ext.Extension):
    """
    TODO: extension class is not yet implemented. In principle, it has to
    provide some restrictive failsafe logic for operating with configuration
    context (see lamia.core.configuration.Stack class). But implementation of
    the full-fledged tag was postponed --- we just use jinja2.ext.do in
    combination with direct operations.
    ...
    An extension manipulating the context stack (Stack class of the
    lamia.core.configuration). Every stack-pushing instruction has to be
    finalized by corresponding stack-popping one.
    """
    tags = set(['context_stack_push', 'context_stack_pop'])

    def __init__(self, environment):
        raise NotImplementedError('See notes in lamia/tests/')
        super(ContextStack, self).__init__(environment)
        #environment.extend(???)

    def parse(self, parser):
        # The parser.stream returns instances of jinja2.lexer.Token.
        tagTok = next( parser.stream )
        while parser.stream.current.type != jinja2.lexer.TOKEN_BLOCK_END:
            tok = next( parser.stream )
        #ctxRef = jinja2.ext.nodes.ContextReference()

