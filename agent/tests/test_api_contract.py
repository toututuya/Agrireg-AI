import inspect

from agrireg_agent.api import create_run, resume_run


def test_background_run_endpoints_are_async():
    assert inspect.iscoroutinefunction(create_run)
    assert inspect.iscoroutinefunction(resume_run)
