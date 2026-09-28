"""Slack reply adapters."""

from __future__ import annotations

from typing import Protocol

from slack_sdk.web.async_client import AsyncWebClient


class ReplyClient(Protocol):
    async def send(self, channel: str, text: str, thread_ts: str | None = None) -> None: ...


class SlackReplyClient:
    def __init__(self, token: str) -> None:
        self.client = AsyncWebClient(token=token)

    async def send(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        await self.client.chat_postMessage(channel=channel, text=text, thread_ts=thread_ts)


class MemoryReplyClient:
    def __init__(self) -> None:
        self.messages: list[dict[str, str | None]] = []

    async def send(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        self.messages.append({"channel": channel, "text": text, "thread_ts": thread_ts})
