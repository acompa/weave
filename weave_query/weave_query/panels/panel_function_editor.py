import dataclasses
import typing

import weave_query as weave
import weave_query
from weave_query import graph, panel

ExpressionType = typing.TypeVar("ExpressionType")


@weave.type()
class FunctionEditorConfig(typing.Generic[ExpressionType]):
    expr: graph.Node[ExpressionType] = dataclasses.field(default_factory=graph.VoidNode)


@weave.type()
class FunctionEditor(panel.Panel):
    id = "FunctionEditor"
    config: FunctionEditorConfig = dataclasses.field(
        default_factory=FunctionEditorConfig
    )
