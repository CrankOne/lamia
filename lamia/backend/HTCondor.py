import logging, os #, htcondor
import lamia.core.filesystem
import lamia.core.templates


"""
The rotuines for task submission on HTCondor clusters steered by BASH script.
"""

def generate_subtree( t, root, task, fs
                    , pathTemplateArgs={}
                    , templateContext={}
                    , renderers={} ):
    """
    Generates directory structure for HTCondor to perform the operations.
    """
    t.deploy_fs_struct( root, fs
                      , pathTemplateArgs=pathTemplateArgs
                      , templateContext=templateContext
                      , renderers=renderers )

