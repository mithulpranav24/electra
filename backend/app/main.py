from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="Electra Multi-Operator EV Charging API",
    description="Backend API for EV Charging Management System",
    version="1.0.0",
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

from app.controllers import auth_controller, user_controller, vehicle_controller

# Routers will be included here as they are developed
app.include_router(auth_controller.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_controller.router, prefix="/api/v1/users", tags=["users"])
app.include_router(vehicle_controller.router, prefix="/api/v1/vehicles", tags=["vehicles"])
