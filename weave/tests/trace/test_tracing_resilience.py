"""
The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

import importlib
from typing import Callable, Iterator

# TODO: Test code capture resilience
# TODO: Test postprocess input/output resilience
import pytest

import weave
from weave.trace import call_context
from weave.trace.context import raise_on_captured_errors
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace_server import trace_server_interface as tsi


class DummyTestException(Exception):
    pass


def assert_no_current_call():
    assert call_context.get_current_call() is None


def test_resilience_to_user_code_errors(client):
    def do_test():
        @weave.op
        def throws():
            raise DummyTestException("This is a test exception")

        throws()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # The user's exception should be raised - even if we're not capturing errors
    with pytest.raises(DummyTestException):
        do_test()

    assert_no_current_call()


class ThrowingServer(tsi.TraceServerInterface):
    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        raise DummyTestException("FAILURE!")

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        raise DummyTestException("FAILURE!")

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        raise DummyTestException("FAILURE!")

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        raise DummyTestException("FAILURE!")

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        raise DummyTestException("FAILURE!")

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        raise DummyTestException("FAILURE!")

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        raise DummyTestException("FAILURE!")

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        raise DummyTestException("FAILURE!")

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise DummyTestException("FAILURE!")

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        raise DummyTestException("FAILURE!")

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise DummyTestException("FAILURE!")

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        raise DummyTestException("FAILURE!")

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        raise DummyTestException("FAILURE!")

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        raise DummyTestException("FAILURE!")

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        raise DummyTestException("FAILURE!")

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        raise DummyTestException("FAILURE!")

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        raise DummyTestException("FAILURE!")

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        raise DummyTestException("FAILURE!")

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        raise DummyTestException("FAILURE!")

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        raise DummyTestException("FAILURE!")

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        raise DummyTestException("FAILURE!")

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        raise DummyTestException("FAILURE!")

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        raise DummyTestException("FAILURE!")

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        raise DummyTestException("FAILURE!")

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        raise DummyTestException("FAILURE!")

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        raise DummyTestException("FAILURE!")


@pytest.mark.skip(
    "TODO: Unskip after Tim's backgrounding PR goes in (add one for the entire eval workflow)"
)
def test_resilience_to_server_errors(client):
    client.server = ThrowingServer()

    def do_test():
        @weave.op
        def simple_op():
            return "hello"

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert res == "hello"

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_patcher_errors(client, log_collector):
    class Module:
        def method(self):
            return 0

    def custom_patcher(m: Callable):
        raise DummyTestException("FAILURE!")

    def do_test():
        test_patcher = MultiPatcher(
            [
                SymbolPatcher(
                    lambda: Module,
                    "method",
                    custom_patcher,
                )
            ]
        )

        test_patcher.attempt_patch()

        return Module().method()

    res = do_test()
    assert res == 0

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Failed to patch")


@pytest.mark.disable_logging_error_check
def test_resilience_to_output_handler_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            return "hello"

        def on_output_handler(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        simple_op._set_on_output_handler(on_output_handler)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert res == "hello"

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_output_handler_errors_async(client, log_collector):
    async def do_test():
        @weave.op
        async def simple_op():
            return "hello"

        def on_output_handler(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        simple_op._set_on_output_handler(on_output_handler)

        return await simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert res == "hello"

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_make_accumulator_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_make_accumulator_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_accumulation_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                raise DummyTestException("FAILURE!")

            return accumulate

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith(
        "Error capturing value from iterator, call data may be incomplete"
    )


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_accumulation_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                raise DummyTestException("FAILURE!")

            return accumulate

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith(
        "Error capturing async value from iterator, call data may be incomplete"
    )


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_should_accumulate_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def should_accumulate(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            should_accumulate=should_accumulate,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_should_accumulate_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def should_accumulate(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            should_accumulate=should_accumulate,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


# Here we are ignoring this warning because the exception IS being raised,
# and that is expected and tested for. It happens to be at the deletion moment
# so pytest is complaining that the exception is not being raised in the
# expected manner.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_on_finish_post_processor_errors(
    client, log_collector
):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def on_finish_post_processor(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            on_finish_post_processor=on_finish_post_processor,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) > 0
    for log in logs:
        assert log.msg.startswith("Error closing iterator, call data may be incomplete")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_on_finish_post_processor_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def on_finish_post_processor(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            on_finish_post_processor=on_finish_post_processor,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) > 0
    for log in logs:
        assert log.msg.startswith("Error closing iterator, call data may be incomplete")


def test_resilience_to_accumulator_internal_errors(client):
    def do_test():
        @weave.op
        def simple_op():
            yield 1
            raise DummyTestException("FAILURE!")

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # User errors should still be raised
    with pytest.raises(DummyTestException):
        list(do_test())

    assert_no_current_call()


@pytest.mark.asyncio
async def test_resilience_to_accumulator_internal_errors_async(client):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            raise DummyTestException("FAILURE!")

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]

    # User errors should still be raised
    with pytest.raises(DummyTestException):
        res = await do_test()
        l = [item async for item in res]

    assert_no_current_call()
