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
Templating system adapter for Lamia.

Uses jinja2 as template-rendering framework to produce dynamic templates.
"""


import yaml, os, fnmatch, logging, datetime, copy, re
#import jinja2schema  # TODO: 1-vars-infer
import jinja2 as j2
import jinja2.lexer, jinja2.ext, jinja2.exceptions, jinja2.nodes
import lamia.core.configuration as LC
import lamia.core.filesystem as FS

from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateRuntimeError

class RaiseExtension(Extension):
    # This is our keyword(s):
    tags = set(['raise'])

    # See also: jinja2.parser.parse_include()
    def parse(self, parser):
        # the first token is the token that started the tag. In our case we
        # only listen to "raise" so this will be a name token with
        # "raise" as value. We get the line number so that we can give
        # that line number to the nodes we insert.
        lineno = next(parser.stream).lineno

        # Extract the message from the template
        message_node = parser.parse_expression()

        return nodes.CallBlock(
            self.call_method('_raise', [message_node], lineno=lineno),
            [], [], [], lineno=lineno
        )

    def _raise(self, msg, caller):
        raise TemplateRuntimeError(msg)

# Template files regex (any file, except hidden ones and swap files produced
# by some editors/IDEs).
rxTemplateFilePat = re.compile(r'^(?P<dir>.+\/)?(?P<filename>[^.~#]\w*)(?:\.(?P<extension>\w+))?$')

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

class RaiseExtension(jinja2.ext.Extension):
    """
    Jinja2 extension to raise exception.
    Despite it violates the general goal of the template-rendering engine, its
    usage might be sometimes justified: when template depends on user's input.
    For implementation details see:
        https://stackoverflow.com/questions/21778252/how-to-raise-an-exception-in-a-jinja2-macro
    """
    # This is our keyword(s):
    tags = set(['raise'])

    # See also: jinja2.parser.parse_include()
    def parse(self, parser):
        # the first token is the token that started the tag. In our case we
        # only listen to "raise" so this will be a name token with
        # "raise" as value. We get the line number so that we can give
        # that line number to the nodes we insert.
        lineno = next(parser.stream).lineno

        # Extract the message from the template
        message_node = parser.parse_expression()

        return jinja2.nodes.CallBlock(
            self.call_method('_raise', [message_node], lineno=lineno),
            [], [], [], lineno=lineno
        )

    def _raise(self, msg, caller):
        raise jinja2.exceptions.TemplateRuntimeError(msg)

class Loader(j2.BaseLoader):
    """
    A custom template loader class for Lamia. Its templates are the YAML files
    and have to be treated correspondingly.
    """
    def _load_yaml_object(self, fPath):  # XXX
        """
        Internal function performing loading the document. Called by
        _discover_templates() and has to return (content, modtime) tuple.
        """
        L = logging.getLogger(__name__)
        with open(fPath) as f:
            try:
                content = yaml.load(f, Loader=yaml.FullLoader)
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

    def _load_template_file(self, fPath):
        L = logging.getLogger(__name__)
        with open(fPath) as f:
            tl = f.read()
        return tl

    def _discover_templates( self, templatesRoot
                           , interpolators=None
                           , ignorePats=['*/README.md'] ):
        """
        Searches for valid Lamia's template documents by given path and loads
        them into returned dict.
        """
        L = logging.getLogger(__name__)
        ret = {}
        for root, dirnames, filenames in os.walk(templatesRoot):
            for mt in filter(lambda t : t[0], map( lambda f: (rxTemplateFilePat.match(f), f), filenames)):
                gd = mt[0].groupdict()
                fPath = os.path.join(root, mt[1])
                if any(map(lambda pat: fnmatch.fnmatch(fPath, pat), ignorePats)):
                    L.debug('File %s excluded by globing pattern(s).'%fPath)
                    continue
                tName = os.path.splitext(os.path.relpath( fPath, templatesRoot ))[0]
                # If it is a .yaml file, try to consider it as our old-style
                # template first:
                if 'yaml' == gd['extension']:
                    # TODO: remove this block once NA58 alignment-monitoring
                    # will entirely switch to ordinary template format.
                    yObj, mt = self._load_yaml_object( fPath )
                    if yObj is not None:
                        ret[tName] = ( LC.Configuration(yObj, interpolators=interpolators)
                                     , fPath, mt)
                        L.debug('Loaded template "%s" from'
                                ' file "%s" (%s)'%( tName, fPath
                                                  , datetime.datetime.fromtimestamp(mt)))
                        continue
                # Otherwise, perform usual loading
                ret[tName] = ( { 'template' : self._load_template_file(fPath) }
                               , fPath
                               , os.path.getmtime(fPath) )
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

    #TODO: 1-vars-infer
    #def infer_template_variables(self):
    #    L = logging.getLogger(__name__)
    #    for k, v in self.templates.items():
    #        try:
    #            sch = jinja2schema.infer( v[0]['template'] )
    #        except Exception as e:
    #            L.error('Failed to infer variables from file "%s":'%v[1] )
    #            L.exception(e)
    #    # NOTE: in order to make this code to work, we have to override the
    #    # template providers of jinja2schema and fool around the default
    #    # settings. See:
    #    #   https://github.com/aromanovich/jinja2schema/tree/master/jinja2schema/visitors

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

class _RecursiveTemplatesHandler(object):
    """
    Common template-rendering handler.
    The template handler instances routes the rendering of a template reference
    to the particular renderer in __call__() method accepting the stream
    instance.
    """
    def __init__( self, renderers={} ):
        self.renderers = renderers

    def __call__( self, template, destStream, path=None
                , context={}, contextHooks={} ):
        L = logging.getLogger('lamia.templates')
        rTxt = None
        if type(template) is str:
            rTxt = self.renderers['default'](template, **context)
        elif type(template) is dict:
            ctxStk = LC.Stack(dict(context))
            # TODO: document context hooks technique
            for ctxHookName in template.get('contextHooks', []):
                ctxh = contextHooks[ctxHookName]
                if callable(ctxh):
                    v = ctxh( template, path, context )
                else:
                    # this case corresponds to somehow manually-injected dict
                    v = ctxh
                ctxStk.push(v, tag=ctxHookName)
            if 'id' in template.keys():
                rTxt = self.renderers[template.get('class', 'default')]( template['id']
                        , **ctxStk)
            elif 'class' in template.keys():
                if template['class'] is not None:
                    rTxt = self.renderers[template.get('class', 'default')]( template
                        , **ctxStk)
                else:
                    return
                    # ^^^ The case of class: None has to remain possible, and
                    # means ``just keep the file as it is''. TODO: similar to "@"
            # TODO: reversed
            #for ctxHookName in template.get('contextHooks', []):
            #    ctxStk.pop(tag=ctxHookName)
        else:
            raise TypeError( 'Expected either a string identifying template'
                    ' or a dictionary with "class" field, not an instance of'
                    ' "%s".'%(type(template)) )
        destStream.write(rTxt)

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
                , additionalFilters={}
                , extensions=[] ):
        L = logging.getLogger(__name__)
        L.info( 'Enabled templates extensions: %s.'%(', '.join(extensions)) )
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
        #
        # Guerilla patch:
        def _get_inherited_template_XXX(_, ast):
            return self.env.parse(self.env.loader.get_source(self.env, ast.template.value)[0])
        # TODO: 1-vars-infer
        #L.info("Applying guerilla patch to `jinja2schema' package...")
        #jinja2schema.visitors.stmt.get_inherited_template = _get_inherited_template_XXX
        L.debug("Infering the template variables.")
        #self.loader.infer_template_variables()  # TODO: 1-vars-infer
        #
        for k, fltr in additionalFilters.items():
            self.env.filters[k] = fltr

    def __call__(self, templateName, **kwargs):
        """
        Renders template identified by templateName, making the
        substitutions acc. to kwargs.
        """
        L = logging.getLogger(__name__)
        #cfg = self.loaderInterpolators['CFG'].dct
        #alb = self.loaderInterpolators['ALBK'].dct
        try:
            t = self.env.get_template(templateName)
            # TODO: put valiadation checks here?
            return t.render( ctx=self.loaderInterpolators, **kwargs)
        except:
            L.error(' ..during rendering of template "%s"'%templateName )
            raise

    def __getitem__(self, k):
        return self.loaderInterpolators[k]

    def deploy_fs_struct( self, root, fs, pathTemplateArgs
                        , renderers={}
                        , templateContext={}
                        , level=None
                        , mode=FS.PathsDeployment.Operation.GENERATE ):
        """
        Performs deployment of filesystem structure subtree according to fiven
        subtree description and template-rendering context.
        @root -- base dir for subtree deployment
        @fs -- subtree manifest (description) document
        @pathTemplateArgs -- template context for path rendering
        @renderers -- supplementary template renderers
        @templateContext -- a dict-like context object for template rendering
        (usually a lamia.core.configuration.Stack object).

        Returns a dictionary of instantiated aliases.
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
        return fs.create_on( root
                , pathCtx=pathTemplateArgs
                , tContext=templateContext
                , leafHandler=_RecursiveTemplatesHandler(renderers=renderers)
                , level=level
                , mode=mode )

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

