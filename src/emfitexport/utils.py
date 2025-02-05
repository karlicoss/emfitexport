from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from .exporthelpers.dal_helper import Json, json_items


# TODO move to dal_helper
def json_items_as_list(*args, **kwargs) -> list[Json]:
    return list(json_items(*args, **kwargs))


# TODO move to dal helper?
if TYPE_CHECKING:
    # just to aid mypy -- it doesn't really behave like a proper Future in runtime
    DummyFutureBase = Future[Any]
else:
    # in principle inheriting from Future in runtime also works
    # but not sure what would happen when we start calling other Future methods
    # so best to keep it simple for now
    DummyFutureBase = object


class DummyFuture(DummyFutureBase):
    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def result(self, *args, **kwargs):  # noqa: ARG002
        return self.fn(*self.args, **self.kwargs)
