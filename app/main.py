import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import controlflow as cf
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.background import ObservationSummary, periodically_check_email, secretary
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background observer processing"""
    # Create necessary directories
    settings.templates_dir.mkdir(exist_ok=True)
    settings.static_dir.mkdir(exist_ok=True)
    settings.summaries_dir.mkdir(exist_ok=True)

    task = asyncio.create_task(periodically_check_email())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title='Information Observer Service', lifespan=lifespan)

# Mount static files using settings
app.mount('/static', StaticFiles(directory=str(settings.static_dir)), name='static')

# Initialize templates with absolute path
templates = Jinja2Templates(directory=str(settings.templates_dir))


@app.get('/')
async def home(request: Request, hours: int = 24):
    """Home page showing recent observations"""
    cutoff = datetime.now() - timedelta(hours=hours)

    summaries = []
    for summary_file in settings.summaries_dir.glob('summary_*.json'):
        summary = ObservationSummary.model_validate_json(summary_file.read_text())
        if summary.timestamp > cutoff:
            summaries.append(summary)

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'summaries': summaries,
            'hours': hours,
            'has_data': bool(summaries),
        },
    )


@app.get('/observations/recent')
async def get_recent_observations(hours: int = 24) -> JSONResponse:
    """Get summaries from recent observations"""
    cutoff = datetime.now() - timedelta(hours=hours)

    # Load recent summaries
    summaries = []
    for summary_file in settings.summaries_dir.glob('summary_*.json'):
        summary = ObservationSummary.model_validate_json(summary_file.read_text())
        if summary.timestamp > cutoff:
            summaries.append(summary)

    if not summaries:
        return JSONResponse(content={'message': 'No recent observations found'}, status_code=200)

    # Use monitor to create aggregate summary
    aggregate_summary = cf.run(
        'Create aggregate summary',
        agent=secretary,
        instructions=f"""
        Review these {len(summaries)} summaries from the past {hours} hours.
        Create a comprehensive overview that:
        1. Highlights the most important items
        2. Groups related information
        3. Notes any patterns or trends
        """,
        context={'summaries': [s.model_dump() for s in summaries]},
        result_type=str,
    )

    return JSONResponse(
        {
            'timespan_hours': hours,
            'summary': aggregate_summary,
            'num_summaries': len(summaries),
            'source_types': list(set(st for s in summaries for st in s.source_types)),
        }
    )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
