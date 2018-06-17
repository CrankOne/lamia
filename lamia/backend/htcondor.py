import logging, os #, htcondor
import lamia.core.filesystem
import lamia.core.templates


"""
The rotuines for task submission on HTCondor custers.
"""

def generate_subtree( t, root, task, fs
                    , pathTemplateArgs={}
                    , templateContext={}
                    , renderers={} ):
    """
    Generates directory structure for HTCondor to perform the operation.
    """
    # We have to inject few additional files, necessary to HTCondor to
    # perform the computation procedure: the DAG file describing task
    # dependencies, and submission files describing jobs to run.
    # ___ Kludge starts here ___
    #   to be located at the `varDir'
    # ...
    # ^^^ Kludge ends here ^^^
    # Now we actually generate the filesystem tree with all the stuff within.
    t.deploy_fs_struct( root, fs
                      , pathTemplateArgs=pathTemplateArgs
                      , templateContext=templateContext
                      , renderers=renderers )

