from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from tarvo.api.document_store import DocumentError
from .service import AssistantService
from .store import AssistantError


class ContextInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    period: str = Field(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$')
    batch_id: str | None = Field(default=None, max_length=100)
    run_id: str | None = Field(default=None, max_length=100)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: str = Field(min_length=1, max_length=6000)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class ConfirmInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: bool


def create_assistant_router(*, store, documents, settings, create_run=None, transport_factory=None):
    """Integration MUST apply application's auth dependency to this router."""
    kwargs = {} if transport_factory is None else {'transport_factory': transport_factory}
    service = AssistantService(store, documents, settings, create_run, **kwargs)
    router = APIRouter(prefix='/api/assistant', tags=['assistant'])
    router.assistant_service = service

    def call(fn, *args):
        try:
            return fn(*args)
        except (AssistantError, DocumentError) as exc:
            return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status, headers={'Cache-Control': 'no-store'})

    @router.get('/context')
    def context():
        return call(service.contexts)

    @router.get('/conversations')
    def conversations():
        return {'items': service.conversations.list(), 'scope': 'workspace_tarvo'}

    @router.post('/conversations', status_code=201)
    def create(body: ContextInput):
        return call(service.create, body.model_dump())

    @router.get('/conversations/{identifier}')
    def get(identifier: str):
        return call(service.conversations.get, identifier)

    @router.post('/conversations/{identifier}/messages')
    def message(identifier: str, body: MessageInput):
        if not body.content.strip():
            return JSONResponse({'error': {'code': 'EMPTY_MESSAGE', 'message': 'Escreva uma pergunta para continuar.'}}, status_code=422)
        return call(service.message, identifier, body.content.strip(), body.request_id)

    @router.post('/conversations/{identifier}/actions/{action_id}')
    def action(identifier: str, action_id: str, body: ConfirmInput):
        if not body.confirm:
            return JSONResponse({'error': {'code': 'CONFIRMATION_REQUIRED', 'message': 'Confira o conjunto e confirme a ação.'}}, status_code=422)
        return call(service.execute, identifier, action_id)

    return router
