# -*- coding: utf-8 -*-
import yaml, os, fnmatch, logging, datetime, copy
import jinja2 as j2
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
                , additionalFilters={} ):
        self.mode = mode
        # Require target dir to be accessible and actually a dir (or a symlink
        # to dir)
        for d in templatesDirs:
            if not os.path.isdir(d):
                raise ValueError( 'Not a directory: "%s".'%d )
        # Set template interpolators, create loader (loads templates instantly,
        # create template-rendering environment)
        self.loaderInterpolators = loaderInterpolators
        self.loader = Loader(templatesDirs, interpolators=self.loaderInterpolators)
        self.env = j2.Environment( loader=self.loader
                , undefined=j2.StrictUndefined )
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
        L = logging.getLogger('lamia.templates')
        if not isinstance(fs, FS.Paths ):
            raise TypeError( "lamia.core.filesystem.Paths object expected"
                    "as TPTH interpolator"
                    ", got %s."%type(fs) )
        if 'default' not in renderers.keys():
            L.warning( 'Template renderer "default" is overriden when'
                    ' deploying FS structure.' )
        renderers['default'] = self
        tContext = copy.copy( templateContext )
        fs.create_on( root
                , pathCtx=pathTemplateArgs
                , tContext=tContext
                , leafHandler=_RecursiveTemplatesHandler(renderers=renderers) )

def render_string( strTmpl, _additionalFilters={}, **kwargs ):
    """
    Renders a string as a anonymous template with existing context.
    """
    loader = kwargs.get('_loader', j2.BaseLoader)
    try:
        e = j2.Environment( loader=loader
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

