from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable
import json
from app.core.config import settings

class UniformResponseRoute(APIRoute):
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
                    # It's safer to re-create the JSONResponse to handle content-length headers correctly
                    return JSONResponse(status_code=response.status_code, content=new_content)
                except Exception:
                    pass
            return response
        return custom_route_handler

app = FastAPI(
    title="Electra Multi-Operator EV Charging API",
    description="Backend API for EV Charging Management System",
    version="1.0.0",
)

app.router.route_class = UniformResponseRoute

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail, "error_code": str(exc.status_code)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal Server Error", "error_code": "500"}
    )

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.environment}

from app.controllers import auth_controller, user_controller, vehicle_controller, wallet_controller, company_controller, station_controller, search_controller, reservation_controller, favorite_controller, waitlist_controller

# Routers will be included here as they are developed
auth_controller.router.route_class = UniformResponseRoute
user_controller.router.route_class = UniformResponseRoute
vehicle_controller.router.route_class = UniformResponseRoute
wallet_controller.router.route_class = UniformResponseRoute
company_controller.router.route_class = UniformResponseRoute
station_controller.router.route_class = UniformResponseRoute
search_controller.router.route_class = UniformResponseRoute
reservation_controller.router.route_class = UniformResponseRoute
favorite_controller.router.route_class = UniformResponseRoute
waitlist_controller.router.route_class = UniformResponseRoute

app.include_router(auth_controller.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_controller.router, prefix="/api/v1/users", tags=["users"])
app.include_router(vehicle_controller.router, prefix="/api/v1/vehicles", tags=["vehicles"])
app.include_router(wallet_controller.router, prefix="/api/v1/wallet", tags=["wallet"])
app.include_router(company_controller.router, prefix="/api/v1/admin/companies", tags=["admin"])
app.include_router(station_controller.router, prefix="/api/v1/operator/stations", tags=["operator"])
app.include_router(search_controller.router, prefix="/api/v1", tags=["search"])
app.include_router(reservation_controller.router, prefix="/api/v1", tags=["reservation"])
app.include_router(favorite_controller.router, prefix="/api/v1", tags=["favorite"])
app.include_router(waitlist_controller.router, prefix="/api/v1", tags=["waitlist"])
