import logging, os #, htcondor
import lamia.core.filesystem
import lamia.core.templates


"""
The rotuines for task submission on LSF clusters steered by BASH script.
"""

def generate_subtree( t, root, task, fs
                    , pathTemplateArgs={}
                    , templateContext={}
                    , renderers={} ):
    """
    Generates directory structure for LSF to perform the operations.
    """
    t.deploy_fs_struct( root, fs
                      , pathTemplateArgs=pathTemplateArgs
                      , templateContext=templateContext
                      , renderers=renderers )


