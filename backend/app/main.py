from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.response import UniformResponseRoute

app = FastAPI(
    title="Electra Multi-Operator EV Charging API",
    description="Backend API for EV Charging Management System",
    version="1.0.0",
)

# Routers set route_class at construction (see app/core/response.py); this
# covers only the routes declared directly on `app`, such as /health.
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

from app.controllers import auth_controller, user_controller, vehicle_controller, wallet_controller, company_controller, station_controller, search_controller, reservation_controller, favorite_controller, waitlist_controller, session_controller, invoice_controller, report_controller, notification_controller, rating_controller, maintenance_controller

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
app.include_router(session_controller.router, prefix="/api/v1", tags=["sessions"])
app.include_router(invoice_controller.router, prefix="/api/v1", tags=["invoices"])
app.include_router(report_controller.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(notification_controller.router, prefix="/api/v1", tags=["notifications"])
app.include_router(rating_controller.router, prefix="/api/v1", tags=["ratings"])
app.include_router(maintenance_controller.router, prefix="/api/v1/operator", tags=["maintenance"])
