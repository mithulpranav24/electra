import json
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class UniformResponseRoute(APIRoute):
    """Wraps successful JSON bodies in the {"success": true, "data": ...} envelope.

    This MUST be passed to APIRouter(route_class=...) at construction time.
    Assigning `router.route_class` after the @router.get/@router.post
    decorators have already run is a silent no-op: the APIRoute objects are
    built by the decorator, so a later reassignment never reaches them.
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response = await original_route_handler(request)
            if hasattr(response, "body") and getattr(response, "status_code", 200) < 400:
                try:
                    content = json.loads(response.body.decode())
                    if isinstance(content, dict) and "success" in content:
                        return response
                    new_content = {"success": True, "data": content}
                    # Re-create the JSONResponse so Content-Length is recomputed.
                    return JSONResponse(status_code=response.status_code, content=new_content)
                except Exception:
                    pass
            return response

        return custom_route_handler
