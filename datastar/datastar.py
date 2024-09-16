from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

from typing_extensions import Protocol

T = TypeVar('T', bound='DatastarEvent')

class EventType(str, Enum):
    FRAGMENT = "datastar-fragment"
    SIGNAL = "datastar-signal"

class MergeType(str, Enum):
    MORPH = "morph_element"
    INNER = "inner_element"
    OUTER = "outer_element"
    PREPEND = "prepend_element"
    APPEND = "append_element"
    BEFORE = "before_element"
    AFTER = "after_element"
    DELETE = "delete_element"
    UPSERT_ATTRIBUTES = "upsert_attributes"

class FragmentConfig(TypedDict, total=False):
    fragment: str
    merge: Optional[MergeType]
    selector: Optional[str]
    settle_duration: Optional[int]
    use_view_transitions: Optional[bool]
    redirect: Optional[str]
    error: Optional[str]

class AsyncDataGenerator(Protocol):
    async def __call__(self) -> AsyncGenerator[Any, None]: ...

@dataclass
class DatastarEvent:
    content: Union[List[Union[str, FragmentConfig]], str, FragmentConfig]
    merge: Optional[MergeType] = None
    selector: Optional[str] = None
    settle_duration: Optional[int] = None
    use_view_transitions: Optional[bool] = None
    redirect: Optional[str] = None
    error: Optional[str] = None
    event_type: EventType = EventType.FRAGMENT

    def __post_init__(self: DatastarEvent) -> None:
        """Validate the content type after initialization."""
        assert isinstance(self.content, (list, str, dict)), "content must be a list, string, or dict"

    @classmethod
    def create_fragment(cls: Type[T], content: Union[List[Union[str, FragmentConfig]], str, FragmentConfig], **kwargs: Any) -> T:
        """
        Create a fragment event.

        Args:
            content: The content for the event.
            **kwargs: Additional keyword arguments for DatastarEvent initialization.

        Returns:
            A DatastarEvent instance (or subclass) configured for a fragment event.
        """
        return cls(content=content, event_type=EventType.FRAGMENT, **kwargs)

    @classmethod
    def create_signal(cls: Type[T], data: Union[Dict[str, Any], str]) -> T:
        """
        Create a signal event.

        Args:
            data: The data for the signal event.

        Returns:
            A DatastarEvent instance (or subclass) configured for a signal event.
        """
        return cls(content=data, event_type=EventType.SIGNAL)

    def _format_fragment_sse(self, fragment: Union[str, FragmentConfig]) -> str:
        """
        Format a fragment for SSE.

        Args:
            fragment: The fragment to format.

        Returns:
            A formatted SSE string for the fragment.
        """
        if isinstance(fragment, dict):
            merge = fragment.get('merge') or self.merge
            selector = fragment.get('selector') or self.selector
            frag = fragment['fragment']
        else:
            merge, selector, frag = self.merge, self.selector, fragment

        data_lines = [
            f"merge {merge.value}" if merge else None,
            f"selector {selector}" if selector else None,
            f"settle {self.settle_duration}" if self.settle_duration else None,
            f"vt {str(self.use_view_transitions).lower()}" if self.use_view_transitions is not None else None,
            f"redirect {self.redirect}" if self.redirect else None,
            f"error {self.error}" if self.error else None,
            f"fragment {frag}"
        ]
        return '\n'.join(f"data: {line}" for line in data_lines if line is not None)

    def _format_signal_sse(self, data: Union[Dict[str, Any], str]) -> str:
        """
        Format a signal for SSE.

        Args:
            data: The signal data to format.

        Returns:
            A formatted SSE string for the signal.
        """
        return f"data: {json.dumps(data) if isinstance(data, dict) else str(data)}"

    def format_sse(self, fragment: Union[str, FragmentConfig]) -> str:
        """
        Format an SSE event.

        Args:
            fragment: The fragment or signal data to format.

        Returns:
            A formatted SSE string.
        """
        data = (self._format_fragment_sse(fragment) if self.event_type == EventType.FRAGMENT
                else self._format_signal_sse(fragment))
        return f"event: {self.event_type.value}\n{data}\n\n"

    async def __aiter__(self) -> AsyncIterator[str]:
        """
        Asynchronously iterate over the content, yielding formatted SSE strings.

        Returns:
            An async iterator yielding formatted SSE strings for each content item.
        """
        if isinstance(self.content, (str, dict)):
            yield self.format_sse(self.content)
        else:
            for item in self.content:
                yield self.format_sse(item)

    def stream(self) -> AsyncIterator[str]:
        """
        Return an asynchronous iterator for the event.

        Returns:
            An async iterator yielding formatted SSE strings.
        """
        return self.__aiter__()

class DatastarStreamer:
    def __init__(self, condition_callable: Callable[[], bool], interval: float = 1.0, sleep_interval: float = 0.1):
        """
        Initialize the DatastarStreamer.

        Args:
            condition_callable: A function that returns a boolean indicating whether to stream or not.
            interval: The interval between yielding fragments.
            sleep_interval: The sleep interval to prevent busy-waiting.
        """
        self.condition_callable = condition_callable
        self.interval = interval
        self.sleep_interval = sleep_interval

    async def stream(self, fragment_generator: Callable[[], AsyncGenerator[Any, None]]) -> AsyncGenerator[str, None]:
        """
        Stream fragments as SSE events.

        Args:
            fragment_generator: A callable that returns an async generator of fragments.

        Yields:
            Formatted SSE strings.
        """
        generator = fragment_generator()
        last_yield_time = 0

        while True:
            try:
                current_time = asyncio.get_event_loop().time()
                if current_time - last_yield_time >= self.interval and self.condition_callable():
                    fragment = await anext(generator)
                    event = DatastarEvent(content=fragment)
                    async for sse_data in event.stream():
                        yield sse_data
                    last_yield_time = current_time
                await asyncio.sleep(self.sleep_interval)
            except StopAsyncIteration:
                break
            except Exception as e:
                print(f"Error in DatastarStreamer: {e}")
                # Depending on your error handling strategy, you might want to yield an error event here

def create_sse_stream(
    data_generator: AsyncDataGenerator,
    merge: Optional[MergeType] = None,
    selector: Optional[str] = None,
    settle_duration: Optional[int] = None,
    use_view_transitions: Optional[bool] = None,
    event_type: EventType = EventType.FRAGMENT,
    interval: float = 1.0
) -> AsyncGenerator[str, None]:
    """
    Create an SSE stream from a data generator.

    Args:
        data_generator: An async generator that yields data for SSE events.
        merge: The merge type for fragment events.
        selector: The selector for fragment events.
        settle_duration: The settle duration for fragment events.
        use_view_transitions: Whether to use view transitions.
        event_type: The type of events to generate.
        interval: The interval between events.

    Returns:
        An async generator yielding formatted SSE strings.
    """
    async def generator() -> AsyncGenerator[str, None]:
        async for data in data_generator():
            event = DatastarEvent(
                content=data,
                merge=merge,
                selector=selector,
                settle_duration=settle_duration,
                use_view_transitions=use_view_transitions,
                event_type=event_type
            )
            async for sse_data in event.stream():
                yield sse_data
            await asyncio.sleep(interval)
    return generator()
