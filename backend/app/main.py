import asyncio
import hashlib
import io
import re
import secrets
import shutil
import threading
import time
import zipfile
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .ai import Provider
from .config import Settings
from .engine import Engine
from .runner import DockerRunner
from .schemas import Approval, Health, Result, UploadResponse
from .security import SafeError, extract_zip
from .workspaces import Store, snapshot_files, snapshot_hash


class RequestGuard:
    """Check origin and bound bodies before framework parsing, including chunked requests."""
    def __init__(self, app, cfg):
        self.app, self.cfg = app, cfg

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        origin = headers.get(b'origin', b'').decode(errors='replace')
        async def reject(status, message):
            await JSONResponse({'detail': message}, status_code=status)(scope, receive, send)
        if origin and origin not in self.cfg.origins:
            return await reject(403, 'Untrusted request origin.')
        limit = self.cfg.max_upload if scope['path'] == '/api/projects/upload' else 4096
        try:
            if int(headers.get(b'content-length', b'0')) > limit:
                return await reject(413, 'Request body exceeds size limit.')
        except ValueError:
            return await reject(400, 'Invalid Content-Length.')
        chunks, size = [], 0
        try:
            async with asyncio.timeout(30):
                while True:
                    event = await receive()
                    if event['type'] == 'http.disconnect':
                        return
                    body = event.get('body', b'')
                    size += len(body)
                    if size > limit:
                        return await reject(413, 'Request body exceeds size limit.')
                    chunks.append(body)
                    if not event.get('more_body'):
                        break
        except TimeoutError:
            return await reject(408, 'Request body timed out.')
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


def create_app(cfg: Settings | None = None, runner=None, provider=None) -> FastAPI:
    cfg = cfg or Settings()
    store = Store(cfg)
    runner = runner or DockerRunner(cfg)
    engine = Engine(runner, provider or Provider(cfg))
    capacity = threading.BoundedSemaphore(1)
    rates = defaultdict(deque)
    rate_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.cleanup()
        yield

    app = FastAPI(title='DevPilot AI', lifespan=lifespan, docs_url='/docs' if cfg.development else None,
                  redoc_url=None, openapi_url='/openapi.json' if cfg.development else None)
    app.state.store = store
    app.add_middleware(RequestGuard, cfg=cfg)
    app.add_middleware(CORSMiddleware, allow_origins=list(cfg.origins), allow_methods=['GET', 'POST'],
                       allow_headers=['Authorization', 'Content-Type', 'X-Filename'])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'detail': 'Invalid request schema.'}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return JSONResponse({'detail': 'Internal service error.'}, status_code=500)

    def rate_limit(request, action, limit):
        client = request.client.host if request.client else 'local'
        with rate_lock:
            times = rates[(client, action)]
            while times and time.monotonic() - times[0] > 60:
                times.popleft()
            if len(times) >= limit:
                raise HTTPException(429, 'Too many requests. Wait one minute.')
            times.append(time.monotonic())

    def authorized(project_id, request):
        if not re.fullmatch('[a-f0-9]{32}', project_id):
            raise HTTPException(404, 'Project not found.')
        project = store.projects.get(project_id)
        auth = request.headers.get('authorization', '')
        token = auth[7:] if auth.startswith('Bearer ') else ''
        if not project or not secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), project.token_hash):
            raise HTTPException(403, 'Project capability is missing or invalid.')
        if time.time() >= project.expires_at:
            raise HTTPException(410, 'Project capability expired. Upload the project again.')
        return project

    def checked_candidate(project):
        try:
            files = snapshot_files(project.root / 'candidate')
            if snapshot_hash(files) != project.candidate_hash:
                raise SafeError('Candidate integrity check failed.')
        except (OSError, SafeError):
            raise HTTPException(409, 'Candidate integrity check failed.') from None
        return files

    @app.get('/api/health', response_model=Health)
    def health():
        available = runner.available()
        return Health(docker_available=available, ai_ready=cfg.mock_ai or bool(cfg.api_key), mock_ai=cfg.mock_ai,
                      model='MOCK' if cfg.mock_ai else cfg.model, max_upload_bytes=cfg.max_upload,
                      message='Sandbox ready.' if available else 'Sandbox execution unavailable. Start Docker Desktop to enable analysis.')

    @app.post('/api/projects/upload', response_model=UploadResponse, status_code=201)
    async def upload(request: Request):
        rate_limit(request, 'upload', 6)
        name = request.headers.get('x-filename', '')
        if not name.lower().endswith('.zip') or len(name) > 120 or not re.fullmatch(r'[A-Za-z0-9_ .-]+', name):
            raise HTTPException(400, 'Provide a .zip filename containing letters, numbers, spaces, dots, underscores or hyphens.')
        if request.headers.get('content-type', '').split(';')[0] != 'application/zip':
            raise HTTPException(415, 'Upload raw ZIP bytes with Content-Type application/zip.')
        if len(store.projects) >= 40:
            raise HTTPException(429, 'Session project limit reached. Restart the backend to clear the session.')
        project, token = store.create(name)
        try:
            extract_zip(await request.body(), project.root / 'original', cfg)
            project.save()
        except SafeError as exc:
            del store.projects[project.result.project_id]
            shutil.rmtree(project.root)
            raise HTTPException(400, str(exc)) from None
        return UploadResponse(project=project.result, capability_token=token, expires_at=project.expires_at)

    @app.post('/api/projects/{project_id}/analyze', response_model=Result, status_code=202)
    def analyze(project_id: str, request: Request, tasks: BackgroundTasks):
        project = authorized(project_id, request)
        rate_limit(request, 'analyze', 4)
        with project.lock:
            if project.result.phase != 'ready':
                raise HTTPException(409, 'This project has already been analyzed. Upload again for another attempt.')
            if not capacity.acquire(blocking=False):
                raise HTTPException(409, 'Another analysis is running. Wait for it to finish.')
            project.result.phase = 'queued'
            project.save()
        def work():
            try:
                engine.analyze(project)
            finally:
                capacity.release()
        tasks.add_task(work)
        return project.result.model_copy(deep=True)

    @app.get('/api/projects/{project_id}/results', response_model=Result)
    def results(project_id: str, request: Request):
        return authorized(project_id, request).result.model_copy(deep=True)

    @app.post('/api/projects/{project_id}/approve', response_model=Result)
    def approve(project_id: str, decision: Approval, request: Request):
        project = authorized(project_id, request)
        with project.lock:
            if project.result.phase not in ('completed', 'failed') or not project.result.diff:
                raise HTTPException(409, 'There is no completed candidate patch to review.')
            if decision.approve and project.result.status != 'VERIFIED':
                raise HTTPException(409, 'Only a verified candidate can be approved for export.')
            if decision.approve:
                checked_candidate(project)
            project.result.approved, project.result.rejected = decision.approve, not decision.approve
            project.save()
        return project.result

    @app.get('/api/projects/{project_id}/download')
    def download(project_id: str, request: Request):
        project = authorized(project_id, request)
        with project.lock:
            if not project.result.approved or project.result.status != 'VERIFIED':
                raise HTTPException(403, 'Approve a verified patch before downloading.')
            files = checked_candidate(project)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as output:
                for name, content in files:
                    output.writestr(name, content)
            return Response(stream.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="devpilot-patched.zip"', 'Cache-Control': 'no-store'})

    return app


app = create_app()
