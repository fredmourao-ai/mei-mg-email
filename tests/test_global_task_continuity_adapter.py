from __future__ import annotations
import importlib.util, os, sys, unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/"scripts"/"agent_task_state.py"

def load_adapter():
    spec=importlib.util.spec_from_file_location("global_task_state_adapter_test",ADAPTER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load continuity adapter")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class GlobalTaskContinuityAdapterTests(unittest.TestCase):
    def setUp(self): self.mod=load_adapter()
    def test_repository_identity_is_pinned(self):
        self.assertEqual(self.mod.REPOSITORY,"fredmourao-ai/mei-mg-email")
    def test_requires_controller_injection(self):
        with mock.patch.dict(os.environ,{},clear=True):
            self.assertFalse(self.mod.controller_path().is_file())
    def test_environment_stamps_repository(self):
        env=self.mod.build_controller_env({"PATH":"/usr/bin"})
        self.assertEqual(env["SHOPVIVALIZ_TASK_REPOSITORY"],"fredmourao-ai/mei-mg-email")
    def test_missing_controller_fails_closed(self):
        with mock.patch.dict(os.environ,{"SHOPVIVALIZ_CONTINUITY_STATE_CLI":"/missing/controller.py"},clear=False):
            with mock.patch.object(sys,"argv",[str(ADAPTER),"show","--task","fixture"]):
                self.assertEqual(self.mod.main(),69)
    def test_self_test_needs_no_controller(self):
        with mock.patch.object(sys,"argv",[str(ADAPTER),"--adapter-self-test"]):
            self.assertEqual(self.mod.main(),0)

if __name__=="__main__":
    unittest.main()
