"""
Regression tests for lamia.core.task.Task's default-value precedence:
CLI argument > user config (`overrideDefaults') > class-level `__defaults'.
Locks in the fix for a bug where set_defaults() unconditionally re-clobbered
any CLI-declared parameter's default back to the class-level value, silently
defeating config-file overrides for any parameter also carrying a class
default (which, in the na58 routines, is most of them -- e.g. `workspace_dir').
"""
import unittest as UT
import lamia.core.task as task


class MinimalTestTask(task.Task, metaclass=task.TaskClass):
    __commonParameters = {
        'workspace_dir' : { 'help' : 'workspace' },
    }
    __execParameters = {
        'tag' : { 'help' : 'tag' },
    }
    __defaults = {
        'workspace_dir' : 'CLASS_DEFAULT',
        # No corresponding CLI-declared parameter at all -- must still reach
        # the namespace via set_defaults()' fallback path.
        'internal_only' : 'CLASS_ONLY_DEFAULT',
    }

    def _main(self, **K):
        self.received = K
        return 0


class TestTaskDefaultsPrecedence(UT.TestCase):
    def test_class_default_used_when_nothing_else_given(self):
        t = MinimalTestTask()
        t.run(args=['--tag', 'x'])
        self.assertEqual(t.received['workspaceDir'], 'CLASS_DEFAULT')
        self.assertEqual(t.received['internalOnly'], 'CLASS_ONLY_DEFAULT')

    def test_cfg_override_beats_class_default(self):
        t = MinimalTestTask()
        t.run(args=['--tag', 'x'], overrideDefaults={'workspace_dir': 'CFG_VALUE'})
        self.assertEqual(t.received['workspaceDir'], 'CFG_VALUE')

    def test_cli_beats_cfg_and_class_default(self):
        t = MinimalTestTask()
        t.run(args=['--tag', 'x', '--workspace-dir', 'CLI_VALUE'],
              overrideDefaults={'workspace_dir': 'CFG_VALUE'})
        self.assertEqual(t.received['workspaceDir'], 'CLI_VALUE')

    def test_cfg_override_with_no_cli_param_is_reported_unused(self):
        t = MinimalTestTask()
        with self.assertLogs(level='WARNING') as logs:
            t.run(args=['--tag', 'x'], overrideDefaults={'no_such_param': 'x'})
        self.assertTrue(any('no_such_param' in m for m in logs.output))


if "__main__" == __name__:
    UT.main()
