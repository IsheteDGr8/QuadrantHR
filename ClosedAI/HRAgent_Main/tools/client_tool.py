"""Client-defined tools: tools defined via JSON spec, executed by external clients.

These tools allow frontend clients (like Agent Canvas) to register tools purely
via JSON in ``POST /conversations``, with no Python code required. When the agent
calls a client tool, an ActionEvent is emitted over the WebSocket and the client
handles execution. The SDK returns an acknowledgment observation immediately.

This eliminates the need for Python tool code in JavaScript repos and the complex
``tool_module_qualnames`` / ``--import-modules`` plumbing.
"""

import copy
import threading
from collections.abc import Sequence
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from runtime.telemetry.logger import get_logger
from security.policies.hr_guardrails import (
    READ_ONLY_BLOCK_MESSAGE,
    conversation_is_read_only,
    is_mutating_hr_tool,
)
from tools.schema import Action, Observation, Schema
from tools.tool import (
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


if TYPE_CHECKING:
    from core.conversation import LocalConversation
    from core.conversation.state import ConversationState
    from tools.spec import Tool


logger = get_logger(__name__)

# ToolDefinition.__call__ only passes (action, conversation). Stash the
# ClientTool's real name so the shared executor can dispatch correctly even
# when Action.kind is a generic/resume class name.
_current_client_tool_name: ContextVar[str | None] = ContextVar(
    "hr_client_tool_name", default=None
)


# ---------------------------------------------------------------------------
# Cached dynamic action types
#
# ``Action.from_mcp_schema`` creates a *concrete* ``Action`` subclass whose
# ``kind`` is derived from the class name (``ClientAction_<name>``). These
# subclasses register process-globally in the discriminated-union hierarchy,
# so creating two classes with the same name (e.g. when the same client tool
# is registered twice, or re-created on conversation resume) makes
# ``Action.resolve_kind`` raise a duplicate-class error and breaks event
# deserialization. We therefore cache the generated type per tool name and
# reject same-name/different-schema conflicts explicitly.
# ---------------------------------------------------------------------------
_client_action_types: dict[str, type[Action]] = {}
_client_action_schemas: dict[str, dict[str, Any]] = {}
_client_tool_names: set[str] = set()
_client_action_lock = threading.RLock()


class ClientToolRegistrationError(ValueError):
    """Raised when client tool registration receives invalid input.

    This is a caller/input error (e.g. a bad ``POST /conversations`` payload),
    so callers such as the agent server map it to a 4xx response rather than a
    500.
    """


class ClientToolSchemaConflictError(ClientToolRegistrationError):
    """Raised when a client tool name is reused with a different schema.

    The generated action ``kind`` (``ClientAction_<name>``) is process-global,
    so a single name cannot represent two different parameter schemas.
    """


def _allow_extra_action_fields(action_type: type[Action]) -> None:
    """Accept additive client-tool fields without rebuilding the Action class.

    Client action ``kind``s are process-global. A later conversation may
    advertise extra optional parameters (e.g. ``send_email.attachments``)
    while an earlier conversation already registered the class. Allowing
    extras keeps both the old events and the new tool calls valid.
    """
    action_type.model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
    )
    action_type.model_rebuild(force=True)


def _get_client_action_type(name: str, schema: dict[str, Any]) -> type[Action]:
    """Return a cached ``Action`` subclass for ``name`` built from ``schema``.

    Reuses the previously generated type when the same ``name`` is requested
    again. The Action class cannot be rebuilt (kind is process-global), so a
    later conversation with extra optional properties reuses the original
    type with ``extra="allow"``. The per-conversation LLM schema still comes
    from ``ClientTool.input_schema``.
    """
    with _client_action_lock:
        existing = _client_action_types.get(name)
        if existing is not None:
            if _client_action_schemas[name] != schema:
                logger.warning(
                    "Client tool %r schema changed; reusing the existing Action "
                    "type and accepting extra fields so new conversations can "
                    "start without a server restart.",
                    name,
                )
                _allow_extra_action_fields(existing)
                _client_action_schemas[name] = copy.deepcopy(schema)
            return existing
        action_type = Action.from_mcp_schema(
            model_name=f"ClientAction_{name}",
            schema=schema,
        )
        _allow_extra_action_fields(action_type)
        _client_action_types[name] = action_type
        _client_action_schemas[name] = copy.deepcopy(schema)
        return action_type


class ClientToolSpec(BaseModel):
    """A tool defined by the client, executed externally (not by the SDK).

    Clients pass these specs in ``POST /conversations`` to register tools
    whose execution is handled outside the SDK (e.g., by a frontend
    listening for ActionEvents over WebSocket).
    """

    name: str = Field(
        ...,
        description="Unique tool name the agent will use to call this tool.",
    )
    description: str = Field(
        ...,
        description=(
            "Description shown to the LLM explaining when and how to use this tool."
        ),
    )
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description=(
            "JSON Schema describing the tool's input parameters. "
            "Must be an object schema."
        ),
    )
    annotations: ToolAnnotations | None = Field(
        default=None,
        description=(
            "Optional MCP-style annotations for the tool. When omitted, the "
            "tool is treated conservatively (not read-only), so the agent is "
            "asked to predict a security risk before calling it."
        ),
    )

    @field_validator("parameters")
    @classmethod
    def _validate_object_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure ``parameters`` is a JSON Schema *object* schema.

        ``ClientTool`` builds a Pydantic action model from this schema via
        ``Action.from_mcp_schema``, which only supports object schemas. Validate
        here so callers get an immediate, clear error at the source instead of a
        confusing failure later during tool creation.
        """
        if v.get("type") != "object":
            raise ValueError(
                "ClientToolSpec.parameters must be an object JSON Schema "
                f"(got type={v.get('type')!r}). Example: "
                '{"type": "object", "properties": {...}}'
            )
        return v


class ClientToolObservation(Observation):
    """Observation returned when a client tool is called.

    The actual execution happens on the client side; the SDK returns
    this acknowledgment so the agent loop can continue.
    """


class ClientToolExecutor(ToolExecutor):
    """Execute client-defined HR action tools on the backend when possible.

    ``list_emails`` / ``list_slack_channels`` read immediately (LOW risk).
    ``send_email`` / ``send_slack_message`` deliver after HITL approval (HIGH risk).
    """

    def __call__(
        self,
        action: Action,
        conversation: "LocalConversation | None" = None,  # noqa: ARG002
    ) -> ClientToolObservation:
        name = _resolve_client_tool_name(action)
        return execute_client_tool(name, action, conversation)


def _resolve_client_tool_name(action: Action) -> str:
    ctx = (_current_client_tool_name.get() or "").strip().lower()
    kind = str(getattr(action, "kind", "") or "")
    cls = type(action).__name__
    blob = f"{ctx} {kind} {cls}".lower().replace("-", "_")
    for candidate in (
        "list_slack_channels",
        "send_slack_message",
        "send_teams_message",
        "list_emails",
        "send_email",
    ):
        if candidate in blob:
            return candidate
    extra = getattr(action, "model_extra", None) or {}
    if getattr(action, "channel", None) or extra.get("channel"):
        if getattr(action, "message", None) or extra.get("message"):
            return "send_slack_message"
        return "list_slack_channels"
    if getattr(action, "to", None) and getattr(action, "subject", None) is not None:
        return "send_email"
    return ctx or kind or cls


def execute_client_tool(
    name: str,
    action: Action,
    conversation: "LocalConversation | None" = None,
) -> ClientToolObservation:
    name_l = (name or "").strip().lower().replace("-", "_")
    extra = getattr(action, "model_extra", None) or {}

    if conversation_is_read_only(conversation) and is_mutating_hr_tool(name_l):
        return ClientToolObservation.from_text(
            text=READ_ONLY_BLOCK_MESSAGE,
            is_error=True,
        )

    if name_l.endswith("list_emails") or name_l == "list_emails":
        max_results = getattr(action, "max_results", None)
        query = getattr(action, "query", None)
        if max_results is None:
            max_results = extra.get("max_results", 10)
        if query is None:
            query = extra.get("query", "in:inbox")
        try:
            from mcp_integration.exceptions import MCPReauthenticationRequiredError
            from mcp_integration.gmail_delivery import (
                format_email_digest,
                list_recent_emails_sync,
            )

            emails = list_recent_emails_sync(
                max_results=int(max_results or 10),
                query=str(query) if query else "in:inbox",
            )
            return ClientToolObservation.from_text(text=format_email_digest(emails))
        except MCPReauthenticationRequiredError:
            return ClientToolObservation.from_text(
                text=(
                    "Gmail is not connected or the OAuth session expired. "
                    "Reconnect Gmail from Tools / MCP Settings, then retry "
                    "list_emails."
                ),
                is_error=True,
            )
        except Exception as exc:
            logger.error("list_emails failed: %s", exc, exc_info=True)
            return ClientToolObservation.from_text(
                text=f"Failed to read Gmail inbox: {exc}",
                is_error=True,
            )

    if name_l.endswith("send_email") or name_l == "send_email":
        to = getattr(action, "to", None) or extra.get("to")
        subject = getattr(action, "subject", None)
        if subject is None:
            subject = extra.get("subject")
        body = getattr(action, "body", None)
        if body is None:
            body = extra.get("body")
        cc = getattr(action, "cc", None) or extra.get("cc")
        attachments = getattr(action, "attachments", None)
        if attachments is None:
            attachments = extra.get("attachments")
        if to and subject is not None and body is not None:
            try:
                from mcp_integration.gmail_delivery import send_gmail_message_sync

                sent = send_gmail_message_sync(
                    to=str(to),
                    subject=str(subject),
                    body=str(body),
                    cc=str(cc) if cc else None,
                    attachments=attachments,
                )
                message_id = sent.get("id", "unknown")
                extra_txt = f" Attachments: {attachments}." if attachments else ""
                return ClientToolObservation.from_text(
                    text=f"Email sent to {to} via Gmail (message id: {message_id}).{extra_txt}"
                )
            except Exception as exc:
                logger.error("send_email delivery failed: %s", exc, exc_info=True)
                return ClientToolObservation.from_text(
                    text=f"Failed to send email via Gmail: {exc}",
                    is_error=True,
                )
        return ClientToolObservation.from_text(
            text="send_email is missing required fields (to, subject, body).",
            is_error=True,
        )

    if "list_slack" in name_l or name_l.endswith("list_slack_channels"):
        limit = getattr(action, "limit", None)
        if limit is None:
            limit = extra.get("limit", 200)
        try:
            from mcp_integration.exceptions import MCPReauthenticationRequiredError
            from mcp_integration.slack_delivery import (
                format_channel_digest,
                list_slack_channels_sync,
            )

            channels = list_slack_channels_sync(limit=int(limit or 200))
            return ClientToolObservation.from_text(text=format_channel_digest(channels))
        except MCPReauthenticationRequiredError:
            return ClientToolObservation.from_text(
                text=(
                    "Slack is not connected or the OAuth session expired. "
                    "Reconnect Slack from MCP Connections, then retry "
                    "list_slack_channels. If the user already named a channel, "
                    "still call send_slack_message with that channel — delivery "
                    "validates the name."
                ),
                is_error=True,
            )
        except Exception as exc:
            logger.error("list_slack_channels failed: %s", exc, exc_info=True)
            return ClientToolObservation.from_text(
                text=(
                    f"Failed to list Slack channels: {exc}. If the user already "
                    "named a channel, call send_slack_message with that name anyway."
                ),
                is_error=True,
            )

    if "send_slack" in name_l or name_l.endswith("send_slack_message"):
        channel = getattr(action, "channel", None) or extra.get("channel")
        message = getattr(action, "message", None) or extra.get("message")
        if channel and message:
            try:
                from mcp_integration.exceptions import MCPReauthenticationRequiredError
                from mcp_integration.slack_delivery import (
                    SlackChannelNotFoundError,
                    send_slack_message_sync,
                )

                sent = send_slack_message_sync(
                    channel=str(channel),
                    message=str(message),
                )
                sent_name = sent.get("name") or sent.get("channel")
                ts = sent.get("ts")
                extra_txt = f" (ts: {ts})" if ts else ""
                return ClientToolObservation.from_text(
                    text=f"Slack message sent to #{sent_name}{extra_txt}."
                )
            except SlackChannelNotFoundError as exc:
                return ClientToolObservation.from_text(text=str(exc), is_error=True)
            except MCPReauthenticationRequiredError:
                return ClientToolObservation.from_text(
                    text=(
                        "Slack is not connected or the OAuth session expired. "
                        "Reconnect Slack from MCP Connections, then retry "
                        "send_slack_message after the user approves."
                    ),
                    is_error=True,
                )
            except Exception as exc:
                logger.error("send_slack_message delivery failed: %s", exc, exc_info=True)
                return ClientToolObservation.from_text(
                    text=f"Failed to send Slack message: {exc}",
                    is_error=True,
                )
        return ClientToolObservation.from_text(
            text="send_slack_message is missing required fields (channel, message).",
            is_error=True,
        )

    logger.error(
        "Unhandled client tool name=%r kind=%r class=%r",
        name,
        getattr(action, "kind", None),
        type(action).__name__,
    )
    return ClientToolObservation.from_text(
        text=(
            f"Client tool {name or type(action).__name__!r} is not implemented "
            "on the server. Retry with list_slack_channels or send_slack_message."
        ),
        is_error=True,
    )

# Shared executor instance — stateless, so one is enough.
_CLIENT_TOOL_EXECUTOR = ClientToolExecutor()


class ClientTool(ToolDefinition[Action, ClientToolObservation]):
    """A tool whose execution is deferred to the external client.

    Created from a :class:`ClientToolSpec` at conversation start. The agent
    sees it as a normal tool and can call it; the ActionEvent is emitted
    over WebSocket for the client to handle.
    """

    client_tool_name: str = Field(
        description="Per-instance tool name from the ClientToolSpec.",
    )
    input_schema: dict[str, Any] = Field(
        description=(
            "The original JSON Schema for the tool's parameters, as provided by "
            "the client. Used verbatim when exporting the tool to the LLM so "
            "client-defined constraints (enum, nested objects, bounds, "
            "additionalProperties, ...) are preserved."
        ),
    )

    @property
    def name(self) -> str:  # type: ignore[override]
        """Return the client-defined tool name."""
        return self.client_tool_name

    def __call__(
        self,
        action: Action,
        conversation: "LocalConversation | None" = None,
    ) -> Observation:
        token = _current_client_tool_name.set(self.client_tool_name)
        try:
            return super().__call__(action, conversation)
        finally:
            _current_client_tool_name.reset(token)

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        """Create a ClientTool from a :class:`ClientToolSpec`.

        Args:
            conv_state: Conversation state (not used).
            **params: Must include ``spec`` — either a :class:`ClientToolSpec`
                instance or a JSON-serializable dict of one. The dict form is
                used when the spec flows through per-conversation
                ``Tool.params`` on the server.

        Returns:
            A single-element sequence containing the ClientTool.
        """
        spec_param = params.get("spec")
        if spec_param is None:
            raise ValueError(
                "ClientTool.create requires a 'spec' parameter "
                "(a ClientToolSpec or a dict of one)."
            )
        if isinstance(spec_param, ClientToolSpec):
            spec = spec_param
        elif isinstance(spec_param, dict):
            spec = ClientToolSpec.model_validate(spec_param)
        else:
            raise TypeError(
                "ClientTool.create 'spec' must be a ClientToolSpec or dict, "
                f"got {type(spec_param)}."
            )

        action_type = _get_client_action_type(spec.name, spec.parameters)

        return [
            cls(
                client_tool_name=spec.name,
                description=spec.description,
                action_type=action_type,
                observation_type=ClientToolObservation,
                executor=_CLIENT_TOOL_EXECUTOR,
                # Leave annotations unset unless the client explicitly provides
                # them: client tools can trigger arbitrary frontend side effects,
                # so we must not optimistically assume read-only/idempotent.
                annotations=spec.annotations,
                input_schema=spec.parameters,
            )
        ]

    @classmethod
    def from_spec(cls, spec: ClientToolSpec) -> "ClientTool":
        """Convenience factory that creates a ClientTool from a spec.

        Returns a single ClientTool instance (not a sequence).
        """
        tools = cls.create(spec=spec)
        return tools[0]

    def _get_tool_schema(
        self,
        add_security_risk_prediction: bool = False,
        action_type: type[Schema] | None = None,
    ) -> dict[str, Any]:
        """Build the provider-facing schema from the original client schema.

        The base implementation rebuilds the schema from the generated Pydantic
        action model, which drops client-defined JSON Schema constraints
        (``enum``, nested ``properties``, ``additionalProperties``, numeric
        bounds, ...). Here we start from the original ``input_schema`` and only
        overlay the SDK-added meta fields (``summary`` and, when applicable,
        ``security_risk``) so client constraints are preserved exactly.
        """
        if action_type is not None:
            raise ValueError(
                "ClientTool._get_tool_schema does not support overriding action_type"
            )

        # Render the SDK meta fields (summary / security_risk) exactly as the
        # base implementation would, then lift just those properties over.
        sdk_schema = super()._get_tool_schema(
            add_security_risk_prediction=add_security_risk_prediction,
        )
        sdk_props: dict[str, Any] = sdk_schema.get("properties", {})
        sdk_required: list[str] = sdk_schema.get("required", []) or []

        merged = copy.deepcopy(self.input_schema)
        merged.setdefault("type", "object")
        props = merged.setdefault("properties", {})
        for meta in ("security_risk", "summary"):
            if meta in sdk_props:
                props[meta] = sdk_props[meta]
                if meta in sdk_required:
                    required = merged.setdefault("required", [])
                    if meta not in required:
                        required.append(meta)

        from tools.tool import _prioritize_schema_fields

        _prioritize_schema_fields(
            schema=merged,
            priority=("security_risk", "summary"),
        )
        return merged

    def to_mcp_tool(
        self,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if input_schema is not None or output_schema is not None:
            raise ValueError(
                "ClientTool.to_mcp_tool does not support overriding schemas"
            )
        return super().to_mcp_tool(
            input_schema=self.input_schema,
            output_schema=self.observation_type.to_mcp_schema()
            if self.observation_type
            else None,
        )


def extract_client_tool_specs(tools: "Sequence[Tool]") -> list[ClientToolSpec]:
    """Recover :class:`ClientToolSpec`s embedded in persisted ``Tool`` specs.

    Client tools carry their full spec under ``Tool.params['spec']`` (see
    :func:`register_client_tools`). When a conversation is resumed in a fresh
    process, that spec is the only place the schema survives, so we use it to
    re-register the dynamic tools. A persisted ``Tool`` is treated as a client
    tool only when its ``params['spec']`` validates as a ``ClientToolSpec`` whose
    ``name`` matches the tool name, which avoids misclassifying ordinary tools
    that happen to use a ``spec`` param.
    """
    from pydantic import ValidationError

    specs: list[ClientToolSpec] = []
    for tool in tools:
        raw = (tool.params or {}).get("spec")
        if not isinstance(raw, dict):
            continue
        try:
            spec = ClientToolSpec.model_validate(raw)
        except ValidationError:
            continue
        if spec.name == tool.name:
            specs.append(spec)
    return specs


def register_client_tools(specs: Sequence[ClientToolSpec]) -> list["Tool"]:
    """Register client-defined tools and return per-conversation tool specs.

    The :class:`ClientTool` *class* (a stateless resolver) is registered once
    per tool name in the global tool registry, while each tool's schema travels
    with the conversation through ``Tool.params`` rather than living in the
    process-global registry. This keeps the resolver stateless so two
    conversations that define the same tool name with the same schema don't
    clobber each other.

    Args:
        specs: The client tool specs to register.

    Returns:
        A list of :class:`~tools.spec.Tool` specs (one per input
        spec) to inject into an agent's ``tools`` so ``_initialize()`` can
        resolve them.
    """
    from tools.registry import list_registered_tools, register_tool
    from tools.spec import Tool

    seen_names: set[str] = set()
    for spec in specs:
        if spec.name in seen_names:
            raise ClientToolRegistrationError(
                f"Duplicate client tool name '{spec.name}' in one registration "
                "request. Client tool names must be unique."
            )
        seen_names.add(spec.name)

    with _client_action_lock:
        tool_specs: list[Tool] = []
        already_registered = set(list_registered_tools())
        for spec in specs:
            collides_with_non_client_tool = (
                spec.name in already_registered and spec.name not in _client_tool_names
            )
            if collides_with_non_client_tool:
                raise ClientToolRegistrationError(
                    f"Client tool name '{spec.name}' collides with an existing "
                    "non-client tool. Choose a unique client tool name."
                )

        for spec in specs:
            _get_client_action_type(spec.name, spec.parameters)
            if spec.name not in already_registered:
                register_tool(spec.name, ClientTool)
                already_registered.add(spec.name)
            _client_tool_names.add(spec.name)
            tool_specs.append(Tool(name=spec.name, params={"spec": spec.model_dump()}))
        return tool_specs
